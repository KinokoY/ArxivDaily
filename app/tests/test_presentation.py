"""Composable content, stage costs and stable recovery snapshots."""
from datetime import timedelta

import pytest

from arxivdaily.config import load_config
from arxivdaily.delivery import MockDelivery
from arxivdaily.llm import AnalysisClient
from arxivdaily.models import DigestItem, ProcessingError, Translation
from arxivdaily.pipeline import Pipeline
from arxivdaily.render import render_archive, render_item, render_notification
from test_llm import FakeClient, FakeResponse, body, config, paper, summary_json
from test_pipeline import NOW, system


def choose(cfg, *modules):
    cfg["presentation"] = {key: key in modules for key in cfg["presentation"]}


def test_default_modules_and_pipeline_have_no_fulltext_or_evidence_calls(tmp_path):
    cfg, fixture, papers, analysis, reader, store, delivery = system(tmp_path)
    cfg["presentation"] = load_config()["presentation"]
    enabled = [key for key, value in cfg["presentation"].items() if value]
    assert enabled == ["title", "title_translation", "abstract", "abstract_translation", "source", "screening_routes"]
    report = Pipeline(cfg, store, None, analysis, reader, delivery, now=NOW).run(papers)
    assert not report["errors"] and report["translation"] == 3
    assert reader.calls == analysis.calls["review"] == analysis.calls["summary"] == 0
    state = store.load()
    for entry in state["digests"][report["digest_id"]]["items"]:
        assert entry["modules"] == enabled and entry["rule_hits"]
        assert entry["summary"] is None
        item = Pipeline._item(state["papers"][entry["paper"]["version_id"].split("v")[0]])
        rendered = render_item(item)
        assert rendered.index("中文标题") < rendered.index("**摘要：") < rendered.index("摘要翻译") < rendered.index("来源") < rendered.index("初筛路径")
        assert rendered.endswith("、".join(entry["rule_hits"]))


@pytest.mark.parametrize("modules", [
    ("title", "source", "screening_routes"),
    ("abstract",), ("title_translation",), ("abstract_translation",),
    ("llm_summary",), ("evidence",),
    ("title", "title_translation", "abstract_translation", "llm_summary", "evidence"),
])
def test_selected_modules_drive_generation_and_rendering(tmp_path, modules):
    cfg, fixture, papers, analysis, reader, store, delivery = system(tmp_path)
    choose(cfg, *modules)
    report = Pipeline(cfg, store, None, analysis, reader, delivery, now=NOW).run(papers[:1])
    assert not report["errors"]
    item = Pipeline._item(store.load()["papers"][papers[0].base_id])
    rendered = render_item(item)
    assert ("**背景：**" in rendered) == ("llm_summary" in modules)
    assert ("**证据链：**" in rendered) == ("evidence" in modules)
    assert ("**摘要：**" in rendered) == ("abstract" in modules)
    assert ("**摘要翻译：**" in rendered) == ("abstract_translation" in modules)
    assert ("**中文标题：**" in rendered) == ("title_translation" in modules)
    assert (papers[0].url in rendered) == ("source" in modules)
    assert (papers[0].title in rendered) == ("title" in modules or "title_translation" in modules)
    assert bool(reader.calls) == bool({"llm_summary", "evidence"}.intersection(modules))
    assert bool(analysis.translation_calls) == bool({"title_translation", "abstract_translation"}.intersection(modules))
    if "llm_summary" in modules and "evidence" not in modules:
        assert item.summary.evidence == []


def test_multiple_custom_screening_routes_are_last_and_not_model_route():
    item = DigestItem(paper(), "translation", modules=["abstract", "screening_routes"],
                      rule_hits=["custom_route", "medical_reasoning", "custom_route"])
    for rendered in (render_archive("2026-10-07", [item]), render_notification("2026-10-07", [item], "https://example.org/a.md")[0]):
        assert "**初筛路径：** custom_route、medical_reasoning" in rendered
        assert rendered.index("**摘要：**") < rendered.index("**初筛路径：**")
        assert paper().title not in rendered and paper().url not in rendered


def test_no_evidence_summary_uses_one_direct_call_and_empty_evidence(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "test-canary")
    data = summary_json()
    data["evidence"] = []
    fake = FakeClient([FakeResponse(data)])
    client = AnalysisClient(config(), fake)
    client._chunks = lambda *_: pytest.fail("evidence chunks must not be generated")
    result = client.summarize(paper(), body(), evidence=False)
    assert result.evidence == [] and len(fake.calls) == 1
    assert '"evidence_enabled": false' in fake.calls[0][1]["json"]["messages"][1]["content"]


def test_long_plain_summary_does_not_automatically_extract_evidence(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "test-canary")
    b = body()
    b.sections[0].text *= 100
    fake = FakeClient([])
    client = AnalysisClient(config(input_chars=1500), fake)
    with pytest.raises(ProcessingError, match="fulltext_exceeds_direct_input_limit"):
        client.summarize(paper(), b, evidence=False)
    assert fake.calls == []


def test_notification_overflow_preserves_complete_module_archive_without_source():
    item = DigestItem(paper(), "translation", translation=Translation("标题", "摘要译文" * 2000),
                      modules=["abstract_translation", "screening_routes"], rule_hits=["one", "two"])
    body_text, modes = render_notification("2026-10-07", [item], "https://example.org/a.md", 500)
    assert len(body_text.encode()) <= 500 and modes[item.paper.base_id] == "translation_archive_link_only"
    assert item.paper.title not in body_text and item.paper.url not in body_text
    assert item.translation.abstract_zh in render_archive("2026-10-07", [item])


def test_failed_translation_and_unknown_delivery_keep_original_modules(tmp_path):
    cfg, fixture, papers, analysis, reader, store, delivery = system(tmp_path, "unknown")
    cfg["presentation"] = load_config()["presentation"]
    class Translator:
        failed = True
        def translate(self, p, *, title_only=False):
            if self.failed and not title_only:
                raise ProcessingError("provider_unavailable")
            return Translation("中文标题", "" if title_only else "中文摘要")
    translator = Translator()
    first = Pipeline(cfg, store, None, analysis, reader, delivery, now=NOW, translator=translator).run(papers[:1])
    assert first["delivery_kind"] == "alert"
    translator.failed = False
    choose(cfg, "title", "llm_summary")
    second = Pipeline(cfg, store, None, analysis, reader, delivery, now=NOW + timedelta(days=1), translator=translator).run([])
    assert second["errors"] == ["delivery_unknown"] and second["translation"] == 1
    entry = store.load()["digests"][second["digest_id"]]["items"][0]
    third = Pipeline(cfg, store, None, analysis, reader, MockDelivery(), now=NOW + timedelta(days=2)).run([])
    recovered = store.load()["digests"][third["digest_id"]]["items"][0]
    assert recovered["modules"] == entry["modules"] and recovered["rule_hits"] == entry["rule_hits"]
    assert recovered["translation"] == entry["translation"] and reader.calls == 0


@pytest.mark.parametrize("value", ['title = "yes"', "title = 1", "unknown_module = true"])
def test_invalid_module_config_rejected(tmp_path, value):
    path = tmp_path / "config.toml"
    path.write_text("[presentation]\n" + value, encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


def test_empty_module_selection_rejected_and_old_workflow_removed(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[presentation]\n" + "\n".join(f"{key} = false" for key in load_config()["presentation"]), encoding="utf-8")
    with pytest.raises(ValueError, match="at least one module"):
        load_config(path)
    path.write_text('[workflow]\nmode = "summary"', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown config key: workflow"):
        load_config(path)
