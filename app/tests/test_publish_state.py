"""Publisher safety checks, including a local bare Git remote transaction."""
import json
import io
from pathlib import Path
import subprocess

import pytest

from scripts import publish_state as publisher


BRANCH = "arxivdaily-state"
REPOSITORY = "reader/digest"
DIGEST_ID = "20261002T071700Z-abcdef12-123456789abc"
SNAPSHOT = f"archive/2026/10/02/{DIGEST_ID}.md"
MANIFEST = f"archive/2026/10/02/{DIGEST_ID}.json"


class FakeGit:
    def __init__(self, directory: Path, *, candidates=(), status=None, remote="base", new_snapshots=(), unchanged=()):
        self.directory = directory
        self.candidates = list(candidates)
        self.status = status or {}
        self.remote = remote
        self.local = "base"
        self.staged = {}
        self.new_snapshots = list(new_snapshots)
        self.unchanged = set(unchanged)
        self.calls = []

    def __call__(self, directory, *args):
        assert directory == self.directory
        self.calls.append(args)
        if args == ("branch", "--show-current"):
            return BRANCH
        if args == ("rev-parse", "HEAD"):
            return self.local
        if args == ("rev-parse", "FETCH_HEAD"):
            return self.remote
        if args[0] == "fetch":
            return ""
        if args[:3] == ("diff", "--cached", "--name-only"):
            return "\n".join(self.staged)
        if args[:4] == ("diff", "--cached", "--no-renames", "--name-status"):
            return "\n".join(f"{status}\t{name}" for name, status in self.staged.items())
        if args[0] == "ls-files":
            return "" if "--ignored" in args else "\n".join(self.candidates)
        if args[0] == "add":
            name = args[-1]
            if name not in self.unchanged:
                self.staged[name] = self.status.get(name, "A")
            return ""
        if args[0] == "show":
            return (self.directory / args[1][1:]).read_text(encoding="utf-8")
        if args[0] == "-c":
            self.local = "new"
            return ""
        if args[0] == "push":
            self.remote = self.local
            return ""
        if args[0] == "diff-tree":
            return "\n".join(self.new_snapshots)
        raise AssertionError(f"unexpected fake Git command: {args}")

    @property
    def pushed(self):
        return any(args[0] == "push" for args in self.calls)


def prepare(tmp_path):
    (tmp_path / "state.json").write_text("{}\n", encoding="utf-8")
    return tmp_path.resolve()


def test_remote_advance_aborts_before_staging_or_push(tmp_path, monkeypatch):
    directory = prepare(tmp_path)
    fake = FakeGit(directory, remote="advanced")
    monkeypatch.setattr(publisher, "git", fake)
    with pytest.raises(RuntimeError, match="advanced remotely"):
        publisher.publish(directory, BRANCH, REPOSITORY, "checkpoint")
    assert not fake.pushed
    assert not any(args[0] == "add" for args in fake.calls)


def test_immutable_snapshot_edit_is_rejected(tmp_path, monkeypatch):
    directory = prepare(tmp_path)
    path = directory / SNAPSHOT
    path.parent.mkdir(parents=True)
    path.write_text("changed", encoding="utf-8")
    fake = FakeGit(directory, candidates=[SNAPSHOT], status={SNAPSHOT: "M", "state.json": "M"})
    monkeypatch.setattr(publisher, "git", fake)
    with pytest.raises(RuntimeError, match="immutable archive"):
        publisher.publish(directory, BRANCH, REPOSITORY, "checkpoint")
    assert not fake.pushed


def test_secret_canary_in_staged_json_blocks_commit(tmp_path, monkeypatch):
    directory = prepare(tmp_path)
    (directory / "state.json").write_text('{"debug":"SECRET-CANARY-123"}', encoding="utf-8")
    fake = FakeGit(directory, status={"state.json": "M"})
    monkeypatch.setattr(publisher, "git", fake)
    monkeypatch.setenv("SERVERCHAN_SENDKEY", "SECRET-CANARY-123")
    with pytest.raises(RuntimeError, match="secret appears"):
        publisher.publish(directory, BRANCH, REPOSITORY, "checkpoint")
    assert not fake.pushed
    assert not any(args[0] == "-c" for args in fake.calls)


def test_credential_shape_blocks_commit_without_matching_environment(tmp_path, monkeypatch):
    directory = prepare(tmp_path)
    (directory / "state.json").write_text('{"debug":"sk-' + 'A' * 32 + '"}', encoding="utf-8")
    fake = FakeGit(directory, status={"state.json": "M"})
    monkeypatch.setattr(publisher, "git", fake)
    with pytest.raises(RuntimeError, match="credential-shaped"):
        publisher.publish(directory, BRANCH, REPOSITORY, "checkpoint")
    assert not fake.pushed


def test_archive_url_mismatch_fails_before_push_or_notification(tmp_path, monkeypatch):
    directory = prepare(tmp_path)
    path = directory / MANIFEST
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"archive_url": "https://example.invalid/wrong.md"}), encoding="utf-8")
    fake = FakeGit(directory, candidates=[MANIFEST], new_snapshots=[MANIFEST])
    monkeypatch.setattr(publisher, "git", fake)
    monkeypatch.setattr(publisher, "urlopen", lambda *_args, **_kwargs: pytest.fail("should not fetch mismatched URL"))
    with pytest.raises(RuntimeError, match="archive URL"):
        publisher.publish(directory, BRANCH, REPOSITORY, "checkpoint")
    assert not fake.pushed


def test_only_public_state_and_archive_files_are_staged(tmp_path, monkeypatch):
    directory = prepare(tmp_path)
    names = [SNAPSHOT, MANIFEST, "archive/2026-10-02.md",
             "archive/2026/10/02/paper.pdf", "archive/2026/10/02/provider.json",
             "archive/2026/10/02/.atomic-tmp.json", "archive/2026/10/02/figure.png"]
    for name in names:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "{}" if name.endswith(".json") else "content"
        if name == MANIFEST:
            content = json.dumps({"archive_url": f"https://raw.githubusercontent.com/{REPOSITORY}/{BRANCH}/{SNAPSHOT}"})
        path.write_text(content, encoding="utf-8")
    (directory / ".run.lock").write_text("lock", encoding="utf-8")
    fake = FakeGit(directory, candidates=names)
    monkeypatch.setattr(publisher, "git", fake)
    publisher.publish(directory, BRANCH, REPOSITORY, "checkpoint")
    staged = {args[-1] for args in fake.calls if args[0] == "add"}
    assert staged == {"state.json", SNAPSHOT, MANIFEST, "archive/2026-10-02.md"}
    assert fake.pushed


def test_noop_checkpoint_does_not_refetch_prior_snapshot(tmp_path, monkeypatch):
    directory = prepare(tmp_path)
    fake = FakeGit(directory, unchanged={"state.json"})
    monkeypatch.setattr(publisher, "git", fake)
    monkeypatch.setattr(publisher, "_verify_archive", lambda *_: pytest.fail("no-op must not verify old snapshot"))
    assert publisher.publish(directory, BRANCH, REPOSITORY, "checkpoint") == "base"
    assert not fake.pushed


def _git(directory: Path, *args: str, input: str | None = None) -> str:
    result = subprocess.run(["git", "-C", str(directory), *args],
                            input=input.encode("utf-8") if input is not None else None,
                            capture_output=True, check=True)
    return result.stdout.decode("utf-8").strip()


def _real_remote(tmp_path: Path) -> tuple[Path, Path]:
    """Build the same one-file orphan root commit used by the workflow."""
    remote = tmp_path / "remote.git"
    source = tmp_path / "source"
    checkout = tmp_path / "checkout"
    remote.mkdir()
    source.mkdir()
    _git(remote, "init", "--bare")
    _git(source, "init", "-b", "main")
    _git(source, "remote", "add", "origin", str(remote))
    state = {"schema_version": 1, "collection": {}, "papers": {}, "runs": [],
             "digests": {}, "chains": {}, "daily": {}, "usage": []}
    blob = _git(source, "hash-object", "-w", "--stdin", input=json.dumps(state) + "\n")
    tree = _git(source, "mktree", input=f"100644 blob {blob}\tstate.json\n")
    commit = _git(source, "-c", "user.name=ArxivDaily", "-c", "user.email=arxivdaily@users.noreply.github.com",
                  "commit-tree", tree, input="Initialize ArxivDaily state\n")
    _git(source, "push", "origin", f"{commit}:refs/heads/{BRANCH}")
    subprocess.run(["git", "clone", "--quiet", "--branch", BRANCH, str(remote), str(checkout)],
                   check=True, capture_output=True, text=True)
    return remote, checkout


def test_real_git_bootstrap_and_snapshot_publish(tmp_path, monkeypatch):
    remote, checkout = _real_remote(tmp_path)
    assert _git(checkout, "ls-files") == "state.json"
    (checkout / "state.json").write_text('{"schema_version": 1, "collection": {}, "papers": {}, "runs": [], "digests": {}, "chains": {}, "daily": {}, "usage": [], "revision": 1}\n', encoding="utf-8")
    markdown = checkout / SNAPSHOT
    markdown.parent.mkdir(parents=True)
    markdown.write_text("# saved digest\n", encoding="utf-8")
    manifest = checkout / MANIFEST
    manifest.write_text(json.dumps({"archive_url": publisher._raw_url(REPOSITORY, BRANCH, SNAPSHOT)}), encoding="utf-8")
    requested = []

    def published_bytes(request, **_kwargs):
        requested.append(request.full_url)
        name = request.full_url.split(f"/{BRANCH}/", 1)[1]
        return io.BytesIO((checkout / name).read_bytes())

    monkeypatch.setattr(publisher, "urlopen", published_bytes)
    oid = publisher.publish(checkout, BRANCH, REPOSITORY, "checkpoint")
    assert oid == _git(remote, "rev-parse", f"refs/heads/{BRANCH}")
    assert set(_git(remote, "ls-tree", "-r", "--name-only", oid).splitlines()) == {"state.json", SNAPSHOT, MANIFEST}
    assert len(requested) == 2
    assert publisher.publish(checkout, BRANCH, REPOSITORY, "noop") == oid
    assert len(requested) == 2


def test_real_git_remote_conflict_keeps_local_checkpoint_unpublished(tmp_path):
    remote, checkout = _real_remote(tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "--quiet", "--branch", BRANCH, str(remote), str(other)],
                   check=True, capture_output=True, text=True)
    (other / "state.json").write_text('{"schema_version": 1, "collection": {}, "papers": {}, "runs": [], "digests": {}, "chains": {}, "daily": {}, "usage": [], "revision": 2}\n', encoding="utf-8")
    _git(other, "add", "state.json")
    _git(other, "-c", "user.name=Other", "-c", "user.email=other@example.invalid", "commit", "-m", "competing checkpoint")
    _git(other, "push", "origin", f"HEAD:refs/heads/{BRANCH}")
    (checkout / "state.json").write_text('{"schema_version": 1, "collection": {}, "papers": {}, "runs": [], "digests": {}, "chains": {}, "daily": {}, "usage": [], "revision": 3}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="advanced remotely"):
        publisher.publish(checkout, BRANCH, REPOSITORY, "checkpoint")
    assert _git(checkout, "diff", "--cached", "--name-only") == ""
    assert '"revision": 3' in (checkout / "state.json").read_text(encoding="utf-8")
    assert '"revision": 2' in _git(remote, "show", f"refs/heads/{BRANCH}:state.json")
