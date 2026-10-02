"""Exercise the real Git candidate boundary, including forced private staging."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess


spec = spec_from_file_location("public_check", Path(__file__).resolve().parents[1] / "scripts" / "check_public_files.py")
public_check = module_from_spec(spec)
spec.loader.exec_module(public_check)


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_ignored_secret_is_private_but_forced_stage_is_rejected(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / ".gitignore").write_text(".secrets/\n", encoding="utf-8")
    private = tmp_path / ".secrets"
    private.mkdir()
    (private / "runtime.json").write_text('{"DEEPSEEK_API_KEY":"local-test-only"}', encoding="utf-8")
    assert public_check.check(tmp_path)[1] == []
    git(tmp_path, "add", "-f", ".secrets/runtime.json")
    assert public_check.check(tmp_path)[1] == [".secrets/runtime.json: private runtime file"]


def test_credential_match_names_file_without_echoing_value(tmp_path):
    git(tmp_path, "init", "-b", "main")
    canary = "sk-" + "A" * 32
    (tmp_path / "mistake.txt").write_text(canary, encoding="utf-8")
    _, findings = public_check.check(tmp_path)
    assert findings == ["mistake.txt: credential-shaped value"]
    assert canary not in str(findings)
