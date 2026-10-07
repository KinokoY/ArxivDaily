import json
from pathlib import Path
import tomllib

import yaml

from arxivdaily.cli import main


def test_workflow_config_generation_preserves_committed_custom_config(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.load((root / ".github/workflows/daily-digest.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["digest"]["steps"]
    prepare = next(step["run"] for step in steps if step["name"] == "Prepare public configuration")
    script = prepare.split("python - <<'PY'\n", 1)[1].split("\nPY", 1)[0]
    app = tmp_path / "app"
    app.mkdir()
    monkeypatch.chdir(app)
    monkeypatch.setenv("REPOSITORY", "reader/digest")
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    config = tmp_path / "config.toml"
    config.write_text('[archive]\npublic_base_url = ""\nstate_branch = "reader-state"\n', encoding="utf-8")
    exec(script, {})
    assert tomllib.loads(config.read_text(encoding="utf-8"))["archive"]["public_base_url"] == "https://raw.githubusercontent.com/reader/digest/reader-state"
    assert output.read_text(encoding="utf-8").strip() == "state_branch=reader-state"
    custom = '[archive]\npublic_base_url = "https://example.org/custom-state"\n'
    config.write_text(custom, encoding="utf-8")
    exec(script, {})
    assert config.read_text(encoding="utf-8") == custom


def test_default_dry_run_cannot_write_normal_state(tmp_path):
    report = tmp_path / "report.json"
    normal = tmp_path / "normal"
    code = main(["run", "--state-dir", str(normal), "--now", "2026-10-02T07:17:00+00:00", "--report", str(report)])
    data = json.loads(report.read_text(encoding="utf-8"))
    assert code == 0 and data["dry_run_isolated"] and not normal.exists()


def test_live_send_requires_public_archive_and_publisher_before_any_io(tmp_path):
    report = tmp_path / "report.json"
    assert main(["run", "--send", "--report", str(report)]) == 2
    data = json.loads(report.read_text(encoding="utf-8"))
    assert "checkpoint" in data["error"]


def test_simulation_rejects_normal_state_directory(tmp_path):
    report = tmp_path / "report.json"
    assert main(["simulate", "--state-dir", str(tmp_path/"normal"), "--report", str(report)]) == 2
    assert "simulation state" in json.loads(report.read_text(encoding="utf-8"))["error"]


def test_missing_send_credentials_fail_before_external_work(tmp_path,monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY",raising=False)
    monkeypatch.delenv("SERVERCHAN_SENDKEY",raising=False)
    config = tmp_path / "config.toml"
    config.write_text('[archive]\npublic_base_url = "https://example.org/state"\n',encoding="utf-8")
    report = tmp_path / "report.json"
    code = main(["run","--send","--config",str(config),"--checkpoint-command","never-execute","--report",str(report)])
    assert code == 2
    error = json.loads(report.read_text(encoding="utf-8"))["error"]
    assert "DEEPSEEK_API_KEY" in error and "SERVERCHAN_SENDKEY" in error


def test_delivery_only_recovery_does_not_require_deepseek_key(tmp_path,monkeypatch):
    from arxivdaily import cli
    from arxivdaily.config import load_config
    from arxivdaily.delivery import MockDelivery
    from arxivdaily.models import parse_time
    from arxivdaily.pipeline import Pipeline
    from arxivdaily.simulation import FixtureAnalysis,FixtureReader,load_fixture
    from arxivdaily.state import StateStore
    app = Path(__file__).resolve().parents[1]
    fixture_path = app/"fixtures/demo.json"
    fixture,papers = load_fixture(fixture_path)
    analysis = FixtureAnalysis(fixture)
    reader = FixtureReader(load_config(),fixture,fixture_path,tmp_path/"raw")
    state_dir = tmp_path/"state"
    Pipeline(load_config(),StateStore(state_dir),None,analysis,reader,MockDelivery("unknown"),now=parse_time("2026-10-02T07:17:00+00:00")).run(papers[:1])
    analysis.calls = {"selection":0,"review":0,"summary":0}
    monkeypatch.delenv("DEEPSEEK_API_KEY",raising=False)
    monkeypatch.setenv("SERVERCHAN_SENDKEY","fake-runtime-sendkey")
    monkeypatch.setattr(cli,"AnalysisClient",lambda config:analysis)
    monkeypatch.setattr(cli,"ServerChan",lambda config:MockDelivery("confirmed"))
    monkeypatch.setattr(cli,"command_publisher",lambda command:lambda:None)
    config_path = tmp_path/"config.toml"
    config_path.write_text('[archive]\npublic_base_url = "https://example.org/state"\n',encoding="utf-8")
    code = main(["run","--send","--retry-stage","delivery","--retry-ids",papers[0].base_id,"--state-dir",str(state_dir),"--config",str(config_path),"--checkpoint-command","mock-only","--report",str(tmp_path/"recovery.json")])
    assert code == 0 and analysis.calls == {"selection":0,"review":0,"summary":0}
