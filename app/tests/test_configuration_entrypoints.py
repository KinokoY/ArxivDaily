"""User edits are loaded consistently and checked without paid requests."""
import json
from pathlib import Path

import pytest

from arxivdaily import cli
from arxivdaily.config import default_config_path, load_config
from arxivdaily.prompts import default_prompt_directory, load_prompts, prompt_fingerprint


def test_root_config_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert default_config_path() == Path(__file__).resolve().parents[2] / "config.toml"
    config = load_config(default_config_path())
    assert Path(config["prompts"]["directory"]) == Path(__file__).resolve().parents[1] / "prompts"


def test_default_cli_uses_configuration_not_internal_defaults(tmp_path, monkeypatch):
    path = tmp_path / "custom.toml"
    path.write_text('[workflow]\nmode = "translation"\n', encoding="utf-8")
    monkeypatch.setattr(cli, "default_config_path", lambda: path)
    report = tmp_path / "report.json"
    assert cli.main(["run", "--report", str(report)]) == 0
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["translation"] == 3 and result["full"] == 0
    assert result["real_delivery"] is False


def test_rule_preview_uses_supplied_categories_and_has_no_provider_requests(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "AnalysisClient", lambda *_: pytest.fail("rule preview instantiated provider"))
    assert cli.main(["config", "--abstract", "Medical spatial reasoning segmentation with DPO.", "--categories", "cs.CV"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert "medical_reasoning" in output["rule_hits"] and output["external_requests"] is False
    assert cli.main(["config", "--abstract", "Medical spatial reasoning segmentation with DPO.", "--categories", "hep-th"]) == 0
    assert json.loads(capsys.readouterr().out)["rule_hits"] == []


def test_relative_prompt_directory_and_missing_prompt_fail_before_live_requests(tmp_path, monkeypatch):
    folder = tmp_path / "my-prompts"
    folder.mkdir()
    for source in default_prompt_directory().glob("*.md"):
        (folder / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    path = tmp_path / "config.toml"
    path.write_text('[prompts]\ndirectory = "my-prompts"\n', encoding="utf-8")
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    assert Path(load_config(path)["prompts"]["directory"]) == folder
    (folder / "summary.md").unlink()
    monkeypatch.setattr(cli, "Collector", lambda *_: pytest.fail("missing prompt caused external collection"))
    report = tmp_path / "report.json"
    assert cli.main(["run", "--live", "--config", str(path), "--report", str(report)]) == 2
    assert "summary.md" in json.loads(report.read_text(encoding="utf-8"))["error"]


def test_review_fingerprint_tracks_interest_and_summary_tracks_section_prompt():
    original = load_prompts(load_config())
    changed = {**original, "selection": original["selection"] + "\n新兴趣"}
    assert prompt_fingerprint(changed, "review") != prompt_fingerprint(original, "review")
    assert prompt_fingerprint(changed, "summary") == prompt_fingerprint(original, "summary")
    changed["section_notes"] += "\n新提取重点"
    assert prompt_fingerprint(changed, "summary") != prompt_fingerprint(original, "summary")


@pytest.mark.parametrize("priority", [[], ["medical_reasoning"] * 5, ["wrong", "medical_objective", "general_rl", "transferable_objective", "general_reasoning"]])
def test_invalid_selection_priorities_are_rejected(tmp_path, priority):
    path = tmp_path / "config.toml"
    path.write_text('[selection]\nroute_priority = ' + json.dumps(priority) + '\n', encoding="utf-8")
    with pytest.raises(ValueError, match="route_priority"):
        load_config(path)
