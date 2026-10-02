"""Atomic local checkpoints with an optional synchronous deployment publisher."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import uuid

from .models import Paper, ProcessingError, fingerprint, iso, utcnow


class PersistenceError(ProcessingError):
    pass


class SecretScrubber:
    """Remove credentials at the public-file boundary, including mock canaries."""
    forbidden = {"api_key", "sendkey", "readkey", "authorization", "reasoning_content", "raw_response", "raw_exception", "image_path"}

    def __init__(self, values=()):
        self.values = sorted({str(v) for v in values if v}, key=len, reverse=True)

    def text(self, text: str) -> str:
        for value in self.values:
            text = text.replace(value, "[REDACTED]")
        text = re.sub(r"(?i)(bearer\s+)[\w.\-]+", r"\1[REDACTED]", text)
        text = re.sub(r"(?i)([?&](?:readkey|sendkey|api_key|token|key)=)[^\s&#)]+", r"\1[REDACTED]", text)
        text = re.sub(r"https://sctapi\.ftqq\.com/[^/\s]+\.send", "https://sctapi.ftqq.com/[REDACTED].send", text)
        return text

    def clean(self, value):
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {k: self.clean(v) for k, v in value.items() if str(k).lower() not in self.forbidden}
        if isinstance(value, (list, tuple)):
            return [self.clean(v) for v in value]
        return value


def empty_state() -> dict:
    return {"schema_version": 1, "collection": {}, "papers": {}, "runs": [], "digests": {}, "chains": {}, "daily": {}, "usage": []}


class StateStore:
    def __init__(self, directory: str | Path, secrets=(), publisher=None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "state.json"
        self.scrubber = SecretScrubber(secrets)
        self.publisher = publisher

    @contextmanager
    def locked(self):
        path = self.directory / ".run.lock"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise PersistenceError("state_locked: another run or an interrupted run holds .run.lock") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"pid": os.getpid(), "started": iso(utcnow())}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            yield
        finally:
            path.unlink(missing_ok=True)

    def load(self) -> dict:
        if not self.path.exists():
            return empty_state()
        try:
            result = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(result,dict):
                raise ValueError("state root must be an object")
            if type(result.get("schema_version")) is not int or result["schema_version"] != 1:
                raise ValueError("unsupported state schema")
            if any(not isinstance(result.get(k), dict) for k in ("papers", "digests", "chains", "daily", "collection")):
                raise ValueError("invalid state structure")
            if any(not isinstance(result.get(k),list) for k in ("runs","usage")):
                raise ValueError("invalid state history")
            return result
        except (ValueError, OSError) as exc:
            raise PersistenceError("state_corrupt: preserve file for inspection") from exc

    def _write(self, path: Path, data: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f".atomic-{uuid.uuid4().hex}"
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            raise PersistenceError("checkpoint_write_failed") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, state: dict) -> None:
        self._write(self.path, json.dumps(self.scrubber.clean(state), ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        if self.publisher:
            try:
                self.publisher()
            except Exception as exc:
                raise PersistenceError(f"checkpoint_publish_failed:{type(exc).__name__}") from None

    def snapshot(self, day: str, digest_id: str, markdown: str, notification: str, manifest: dict) -> str:
        # digest IDs are constructed internally; validate before file operations.
        datetime.strptime(day, "%Y-%m-%d")
        if not re.fullmatch(r"[a-zA-Z0-9\-]+", digest_id):
            raise ValueError("invalid digest ID")
        relative = f"archive/{day.replace('-', '/')}/{digest_id}.md"
        files = {relative: self.scrubber.text(markdown), relative.removesuffix(".md") + ".notification.md": self.scrubber.text(notification), relative.removesuffix(".md") + ".json": json.dumps(self.scrubber.clean(manifest), ensure_ascii=False, sort_keys=True, indent=2) + "\n"}
        for name, text in files.items():
            path = self.directory / name
            if path.exists():
                if path.read_text(encoding="utf-8") != text:
                    raise PersistenceError("immutable_snapshot_conflict")
            else:
                self._write(path, text)
        index = self.directory / f"archive/{day}.md"
        current = index.read_text(encoding="utf-8") if index.exists() else f"# arXiv 每日简报 · {day}\n\n"
        link = f"- [{digest_id}]({day.replace('-', '/')}/{digest_id}.md)"
        if link not in current:
            self._write(index, current + link + ("（补发，上一轮投递未确认）" if manifest.get("recovery_of") else "") + "\n")
        return relative


def command_publisher(command: str):
    """JSON argv recommended on Windows; never invoke a shell or expose output."""
    argv = json.loads(command) if command.lstrip().startswith("[") else shlex.split(command, posix=True)
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) for x in argv):
        raise ValueError("checkpoint command must be a command or JSON argv")

    def publish():
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
        if result.returncode:
            raise PersistenceError("publisher_nonzero_exit")

    return publish


def upsert_paper(state: dict, paper: Paper, now: datetime, hits: list[str]) -> dict:
    key = paper.base_id
    records = state["papers"]
    if key not in records:
        records[key] = {"paper": paper.to_dict(), "first_discovered": iso(now), "versions": [paper.version_id], "rule_hits": hits, "attempts": {}, "failures": {}, "events": [], "stage": "candidate"}
    else:
        record = records[key]
        if paper.version_id not in record["versions"]:
            record["versions"].append(paper.version_id)
        record["latest_version"] = paper.version_id
        record["rule_hits"] = sorted(set(record["rule_hits"]) | set(hits))
        # Keep the exact processed version and its validated summary stable.
        if record["stage"] == "candidate" and not record.get("decision"):
            record["paper"] = paper.to_dict()
    return records[key]


def confirmed(record: dict) -> bool:
    return any(event.get("status") == "confirmed" and event.get("kind") in {"normal", "promotion", "resend"} for event in record.get("events", []))


def body_metadata(body) -> dict:
    return {"version_id": body.version_id, "source_url": body.source_url, "source_type": body.source_type, "quality": body.quality, "locators": [s.locator for s in body.sections], "figures": [{"label": f.label, "locator": f.locator, "required": f.required, "rendered": bool(f.image_path)} for f in body.figures]}
