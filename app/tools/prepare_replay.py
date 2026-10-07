"""Prepare four version-pinned public arXiv replay fixtures with provenance.

Metadata and each source result are checkpointed to a workspace manifest.
Reruns reuse verified local sources and resume failed downloads.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.client import IncompleteRead
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arxivdaily.collection import Collector  # noqa: E402
from arxivdaily.config import load_config  # noqa: E402
from arxivdaily.models import Paper, iso  # noqa: E402


REPLAY_IDS = ("2308.00692v3", "2504.11008v2", "2505.11872v4", "2603.19169v1")
USER_AGENT = "ArxivDaily replay fixture preparation/1.0 (public academic sources)"
RETRYABLE_HTTP = {408, 429, 500, 502, 503, 504}


def _save_manifest(path: Path, manifest: dict) -> None:
    manifest["updated_at"] = iso(datetime.now(timezone.utc))
    manifest["complete"] = all(
        not entry["failures"]
        and any(source["kind"] == "pdf" for source in entry["sources"])
        and (any(source["kind"] == "html" for source in entry["sources"]) or any(source["kind"] == "html" for source in entry["unavailable"]))
        for entry in manifest["papers"]
    )
    temporary = path.with_name(path.name + ".part")
    try:
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _metadata(output_dir: Path, collector: Collector) -> dict:
    path = output_dir / "manifest.json"
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        entries = manifest.get("papers", [])
        if {item.get("version_id") for item in entries} != set(REPLAY_IDS):
            raise ValueError("saved manifest does not contain the four pinned versions")
        for item in entries:
            paper = Paper.from_dict(item["metadata"])
            if paper.version_id != item["version_id"]:
                raise ValueError("saved manifest metadata version mismatch")
            item.setdefault("sources", [])
            item.setdefault("unavailable", [])
            item.setdefault("failures", [])
        manifest["papers"] = sorted(entries, key=lambda item: REPLAY_IDS.index(item["version_id"]))
        return manifest

    papers = collector.by_ids(REPLAY_IDS)
    actual = {paper.version_id for paper in papers}
    expected = set(REPLAY_IDS)
    if actual != expected:
        raise ValueError(f"replay metadata version mismatch; missing={sorted(expected - actual)}, extra={sorted(actual - expected)}")
    by_id = {paper.version_id: paper for paper in papers}
    manifest = {
        "schema_version": 2,
        "created_at": iso(datetime.now(timezone.utc)),
        "complete": False,
        "papers": [
            {"version_id": identifier, "base_id": by_id[identifier].base_id,
             "metadata": by_id[identifier].to_dict(), "sources": [], "unavailable": [], "failures": []}
            for identifier in REPLAY_IDS
        ],
    }
    _save_manifest(path, manifest)  # Durable before the first body request.
    return manifest


def _source_url(kind: str, identifier: str) -> str:
    return f"https://arxiv.org/{kind}/{identifier}"


def _validate(kind: str, content: bytes, content_type: str, identifier: str) -> None:
    if kind == "pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError(f"{identifier} PDF response is not a PDF")
    elif not (content_type in {"text/html", "application/xhtml+xml"} and b"<html" in content[:4096].lower()):
        raise ValueError(f"{identifier} HTML response is not HTML")


def _cached_source(output_dir: Path, entry: dict, kind: str, max_bytes: int) -> dict | None:
    path = output_dir / f"{entry['version_id']}.{kind}"
    if not path.exists():
        return None
    if path.stat().st_size > max_bytes:
        raise ValueError(f"cached {kind} exceeds source size limit")
    content = path.read_bytes()
    old = next((source for source in entry["sources"] if source["kind"] == kind), None)
    content_type = old.get("content_type", "") if old else ("application/pdf" if kind == "pdf" else "text/html")
    _validate(kind, content, content_type, entry["version_id"])
    digest = hashlib.sha256(content).hexdigest()
    if old and old["sha256"] != digest:
        raise ValueError(f"cached {kind} hash mismatch for {entry['version_id']}")
    record = dict(old or {})
    record.update({
        "kind": kind, "url": _source_url(kind, entry["version_id"]),
        "resolved_url": record.get("resolved_url", _source_url(kind, entry["version_id"])),
        "path": path.name, "sha256": digest, "bytes": len(content), "content_type": content_type,
        "retrieved_at": record.get("retrieved_at", iso(datetime.fromtimestamp(path.stat().st_mtime, timezone.utc))),
    })
    return record


def _fetch(url: str, *, opener: Callable[..., Any], max_bytes: int, timeout: int) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf"})
    with opener(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError(f"source exceeds {max_bytes} bytes")
        return content, content_type, response.geturl()


def _write_source(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".part")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _replace_kind(entry: dict, key: str, kind: str, value: dict | None) -> None:
    entry[key] = [item for item in entry[key] if item["kind"] != kind]
    if value is not None:
        entry[key].append(value)


def prepare_replay(
    output_dir: Path,
    *,
    collector: Collector,
    opener: Callable[..., Any] = urlopen,
    min_interval: float = 3.0,
    timeout: int = 90,
    max_bytes: int = 25_000_000,
    attempts: int = 3,
    backoff_seconds: float = 2.0,
) -> dict:
    """Resume four pinned sources; report failures without losing metadata."""
    if min_interval < 3.0 and opener is urlopen:
        raise ValueError("real source requests must be at least 3 seconds apart")
    if timeout <= 0 or attempts < 1 or backoff_seconds < 0:
        raise ValueError("invalid network retry settings")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "manifest.json"
    manifest = _metadata(output_dir, collector)
    _save_manifest(path, manifest)
    last_request_end = time.monotonic()  # Last metadata API request, if any.
    for entry in manifest["papers"]:
        identifier = entry["version_id"]
        for kind in ("html", "pdf"):
            try:
                cached = _cached_source(output_dir, entry, kind, max_bytes)
            except (OSError, ValueError) as exc:
                _replace_kind(entry, "failures", kind, {"kind": kind, "error": type(exc).__name__, "attempts": 0, "at": iso(datetime.now(timezone.utc))})
                _save_manifest(path, manifest)
                continue
            if cached:
                _replace_kind(entry, "sources", kind, cached)
                _replace_kind(entry, "failures", kind, None)
                _replace_kind(entry, "unavailable", kind, None)
                _save_manifest(path, manifest)
                continue
            # A manifest record alone does not prove the local body still
            # exists. Remove stale references before attempting its download.
            _replace_kind(entry, "sources", kind, None)
            _save_manifest(path, manifest)
            if any(item["kind"] == kind for item in entry["unavailable"]):
                continue  # Known 404/406/410 HTML conversion absence.
            url = _source_url(kind, identifier)
            for attempt in range(1, attempts + 1):
                wait = min_interval - (time.monotonic() - last_request_end)
                if wait > 0:
                    time.sleep(wait)
                try:
                    content, content_type, resolved_url = _fetch(url, opener=opener, max_bytes=max_bytes, timeout=timeout)
                    _validate(kind, content, content_type, identifier)
                    destination = output_dir / f"{identifier}.{kind}"
                    _write_source(destination, content)
                    _replace_kind(entry, "sources", kind, {
                        "kind": kind, "url": url, "resolved_url": resolved_url,
                        "path": destination.name, "sha256": hashlib.sha256(content).hexdigest(),
                        "bytes": len(content), "content_type": content_type,
                        "retrieved_at": iso(datetime.now(timezone.utc)),
                    })
                    _replace_kind(entry, "failures", kind, None)
                    _replace_kind(entry, "unavailable", kind, None)
                    break
                except HTTPError as exc:
                    if kind == "html" and exc.code in {404, 406, 410}:
                        _replace_kind(entry, "unavailable", kind, {"kind": kind, "http_status": exc.code, "url": url})
                        _replace_kind(entry, "failures", kind, None)
                        break
                    _replace_kind(entry, "failures", kind, {"kind": kind, "error": "HTTPError", "http_status": exc.code, "attempts": attempt, "at": iso(datetime.now(timezone.utc))})
                    if exc.code not in RETRYABLE_HTTP:
                        break
                except (TimeoutError, URLError, IncompleteRead, OSError, ValueError) as exc:
                    _replace_kind(entry, "failures", kind, {"kind": kind, "error": type(exc).__name__, "attempts": attempt, "at": iso(datetime.now(timezone.utc))})
                    if isinstance(exc, ValueError):
                        break  # Invalid content or size will not improve on retry.
                finally:
                    last_request_end = time.monotonic()
                    _save_manifest(path, manifest)
                if attempt < attempts:
                    time.sleep(backoff_seconds * 2 ** (attempt - 1))
    _save_manifest(path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[2] / "config.toml", help="public TOML config; defaults to the repository config")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "fixtures" / "sources")
    parser.add_argument("--timeout", type=int, default=90, help="seconds per source request (60 or 90 suggested)")
    parser.add_argument("--attempts", type=int, default=3, help="maximum attempts per source")
    parser.add_argument("--backoff-seconds", type=float, default=2.0)
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        result = prepare_replay(
            args.output, collector=Collector(config), timeout=args.timeout,
            attempts=args.attempts, backoff_seconds=args.backoff_seconds,
            max_bytes=int(config["fulltext"]["max_download_bytes"]),
        )
    except Exception as exc:
        print(f"Replay preparation stopped before completion: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
    sources = sum(len(entry["sources"]) for entry in result["papers"])
    failures = sum(len(entry["failures"]) for entry in result["papers"])
    print(f"Replay metadata saved: {len(result['papers'])} papers; sources: {sources}; failures: {failures}; complete: {result['complete']}")
    if not result["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
