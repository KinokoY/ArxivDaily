"""Publish one checkpoint from a dedicated state checkout.

This executable is intended for Actions, never for an offline dry run. It
deliberately rejects a remotely advanced branch instead of silently merging
or replacing another writer's state. Workflow concurrency prevents routine
overlap; the remote check protects manual writers and out-of-band races.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote
from urllib.request import Request, urlopen


_DIGEST_FILE = re.compile(
    r"archive/\d{4}/\d{2}/\d{2}/"
    r"\d{8}T\d{6}Z-[0-9a-f]{8}-(?:alert-)?[0-9a-f]{12}"
    r"(?:\.md|\.notification\.md|\.json)"
)
_CREDENTIAL_SHAPES = (
    re.compile(r"\bsk-[A-Za-z0-9]{24,}\b"),
    re.compile(r"\bSCT\d{5,}[A-Za-z0-9]{16,}\b"),
)


def _public_archive_name(name: str) -> bool:
    return bool(name == "archive/papers.md" or re.fullmatch(r"archive/\d{4}-\d{2}-\d{2}\.md", name) or _DIGEST_FILE.fullmatch(name))


def _raw_url(repository: str, branch: str, name: str) -> str:
    return "https://raw.githubusercontent.com/" + repository + "/" + quote(branch, safe="") + "/" + quote(name, safe="/")


def git(directory: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(directory), *args],
        check=False, capture_output=True, text=True, encoding="utf-8",
    )
    if completed.returncode:
        # Git's stderr may contain credential-bearing remote URLs. Never echo
        # it into Actions logs or a public job summary.
        raise RuntimeError(f"git {args[0]} failed (exit {completed.returncode})")
    return completed.stdout.strip()


def remote_oid(directory: Path, branch: str) -> str:
    git(directory, "fetch", "--quiet", "origin", f"refs/heads/{branch}")
    return git(directory, "rev-parse", "FETCH_HEAD")


def _verify_archive(directory: Path, repository: str, branch: str, commit: str) -> None:
    changed = git(directory, "diff-tree", "--no-commit-id", "--name-only", "--diff-filter=A", "-r", commit)
    snapshots = [name for name in changed.splitlines() if _DIGEST_FILE.fullmatch(name)]
    for name in snapshots:
        expected = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        url = _raw_url(repository, branch, name)
        if name.endswith(".json"):
            manifest = json.loads((directory / name).read_text(encoding="utf-8"))
            markdown_path = name.removesuffix(".json") + ".md"
            expected_archive_url = _raw_url(repository, branch, markdown_path)
            if manifest.get("archive_url") != expected_archive_url:
                raise RuntimeError("archive URL in snapshot manifest does not match the public state branch")
        for attempt in range(4):
            try:
                with urlopen(Request(url, headers={"User-Agent": "ArxivDaily-state-publisher"}), timeout=12) as response:
                    actual = hashlib.sha256(response.read()).hexdigest()
                if actual == expected:
                    break
            except Exception:
                pass
            if attempt < 3:
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError("new public archive snapshot is not yet reachable with matching bytes")


def publish(directory: Path, branch: str, repository: str, message: str) -> str:
    directory = directory.resolve(strict=True)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("repository must be owner/name")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch) or ".." in branch or branch.endswith("/"):
        raise ValueError("invalid state branch")
    if not message or "\n" in message:
        raise ValueError("single-line commit message required")
    if git(directory, "branch", "--show-current") != branch:
        raise RuntimeError("state checkout is not on the configured branch")
    base = git(directory, "rev-parse", "HEAD")
    if remote_oid(directory, branch) != base:
        raise RuntimeError("state branch advanced remotely; abort checkpoint and reload latest state")
    if git(directory, "diff", "--cached", "--name-only"):
        raise RuntimeError("state checkout already has staged changes; refusing to publish unrelated files")
    state_file = directory / "state.json"
    if not state_file.is_file() or state_file.is_symlink():
        raise RuntimeError("state.json is missing; refusing to publish an incomplete checkpoint")
    json.loads(state_file.read_text(encoding="utf-8"))
    git(directory, "add", "--", "state.json")
    if (directory / ".gitignore").is_file():
        git(directory, "add", "--", ".gitignore")
    archive_names = set(git(directory, "ls-files", "--modified", "--deleted", "--others",
                            "--exclude-standard", "--", "archive").splitlines())
    archive_names.update(git(directory, "ls-files", "--others", "--ignored",
                             "--exclude-standard", "--", "archive").splitlines())
    for name in sorted(archive_names):
        if not _public_archive_name(name):
            continue
        if any(part.startswith(".atomic-") or part == ".run.lock" for part in name.split("/")):
            continue
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("an existing public archive file was removed")
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            manifest = json.loads(content)
            markdown_path = name.removesuffix(".json") + ".md"
            if manifest.get("archive_url") != _raw_url(repository, branch, markdown_path):
                raise RuntimeError("archive URL in snapshot manifest does not match the public state branch")
        git(directory, "add", "--force", "--", name)
    changes = git(directory, "diff", "--cached", "--no-renames", "--name-status").splitlines()
    for change in changes:
        status, _, name = change.partition("\t")
        if status != "A" and _DIGEST_FILE.fullmatch(name):
            raise RuntimeError("immutable archive snapshot was changed or removed")
        if status != "D":
            staged = git(directory, "show", f":{name}")
            if any(pattern.search(staged) for pattern in _CREDENTIAL_SHAPES):
                raise RuntimeError("a credential-shaped value appears in staged public state")
            for env_name in ("DEEPSEEK_API_KEY", "TRANSLATION_API_KEY", "SERVERCHAN_SENDKEY", "GITHUB_TOKEN"):
                secret = os.environ.get(env_name)
                if secret and len(secret) >= 8 and secret in staged:
                    raise RuntimeError("a configured secret appears in staged public state")
    if git(directory, "diff", "--cached", "--name-only"):
        git(directory, "-c", "user.name=ArxivDaily", "-c", "user.email=arxivdaily@users.noreply.github.com",
            "commit", "--quiet", "-m", message)
    commit = git(directory, "rev-parse", "HEAD")
    if remote_oid(directory, branch) != base:
        raise RuntimeError("state branch changed before push; local checkpoint retained for recovery")
    if commit != base:
        git(directory, "push", "--quiet", "origin", f"HEAD:refs/heads/{branch}")
    if remote_oid(directory, branch) != commit:
        raise RuntimeError("pushed checkpoint could not be verified on remote")
    # Only a new checkpoint can introduce a new snapshot. A pipeline may call
    # this command many times with no file changes; do not fetch the prior
    # commit's archive files on every no-op callback.
    if commit != base:
        _verify_archive(directory, repository, branch, commit)
    return commit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--message", required=True)
    args = parser.parse_args()
    try:
        commit = publish(args.state_dir, args.branch, args.repository, args.message)
    except (ValueError, RuntimeError, OSError, UnicodeError) as exc:
        print(f"State checkpoint failed: {exc}", file=sys.stderr)
        return 1
    print(f"State checkpoint published: {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
