import json
import logging
import time
from copy import deepcopy

import pytest

from arxivdaily.llm import AnalysisClient, validate_summary
from arxivdaily.models import Body, Decision, Evidence, Paper, ProcessingError, Section, Summary
from arxivdaily.state import PersistenceError
from arxivdaily.prompts import default_prompt_directory


class FakeResponse:
    status_code = 200

    def __init__(self, content, finish="stop", usage="default", message=None):
        self.content = content
        self.finish = finish
        self.usage = usage
        self.message = message

    def raise_for_status(self):
        pass

    def json(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "prompt_cache_hit_tokens": 20, "completion_tokens_details": {"reasoning_tokens": 30}} if self.usage == "default" else self.usage
        message = {"content": json.dumps(self.content, ensure_ascii=False)} if self.message is None else self.message
        return {"model": "deepseek-flash", "system_fingerprint": "fp_123", "usage": usage, "choices": [{"finish_reason": self.finish, "message": message}]}


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def paper():
    return Paper("2504.11008v2", "Mask paper", "We use a mask predictor with a preference objective in medical images.", ["cs.CV"], "2025-04-15T00:00:00+00:00", "2025-05-01T00:00:00+00:00")


def body():
    method = "We train a topology-aware mask predictor with paired positive and negative segmentation masks."
    evaluation = "On held-out images the method improves Dice to 0.85 compared with 0.80 for the baseline."
    appendix = "The appendix shows that small vessels remain difficult and reports a separate patient subgroup."
    sections = [Section("section:Method", method), Section("section:Experiments", evaluation), Section("section:Appendix", appendix)]
    return Body("2504.11008v2", "https://arxiv.org/html/2504.11008v2", "html", sections, quality={"passed": True, "read_locators": [s.locator for s in sections]})


def decision_json(**changes):
    data = {"status": "select", "route": "medical_reasoning", "tier": "full", "reason": "The method directly predicts medical masks.", "abstract_evidence": ["mask predictor with a preference objective"], "uncertainty": [], "rl_is_method": False, "dpo_is_method": True, "theory_evidence": False, "transfer_evidence": False, "score": 84}
    data.update(changes)
    return data


def summary_json():
    b = body()
    method, evaluation, appendix = [s.text for s in b.sections]
    return {"background": "医学图像掩码存在困难。", "contribution": "提出拓扑感知分割目标。", "method": "使用成对正负掩码训练预测器。", "experiments": "留出数据的 Dice 为 0.85。", "conclusion": "小血管仍有困难。", "evidence": [
        {"field": "background", "locator": "section:Appendix", "quote": appendix, "source_url": b.source_url},
        {"field": "contribution", "locator": "section:Method", "quote": method, "source_url": b.source_url},
        {"field": "method", "locator": "section:Method", "quote": method, "source_url": b.source_url},
        {"field": "experiments", "locator": "section:Experiments", "quote": evaluation, "source_url": b.source_url},
        {"field": "conclusion", "locator": "section:Appendix", "quote": appendix, "source_url": b.source_url},
    ]}


def config(input_chars=70000):
    return {"llm": {"filter": {"api_key_env": "TEST_LLM_KEY", "attempts": 1, "retry_delay_seconds": 0}, "summary": {"api_key_env": "TEST_LLM_KEY", "attempts": 1, "retry_delay_seconds": 0, "input_chars": input_chars, "chunk_chars": 1000}, "pricing": {"cache_hit_per_million": 0, "cache_miss_per_million": 0, "output_per_million": 0}}}


def test_select_high_thinking_and_safe_usage(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    fake = FakeClient([FakeResponse(decision_json())])
    analysis = AnalysisClient(config(), fake)
    decision = analysis.select(paper(), ["medical mask"])
    assert decision.status == "select"
    _, call = fake.calls[0]
    assert call["json"]["thinking"] == {"type": "enabled"}
    assert call["json"]["reasoning_effort"] == "high"
    assert analysis.usage_records[0]["reasoning_tokens"] == 30
    assert analysis.usage_records[0]["estimated_cost"] is None
    assert "secret-canary" not in json.dumps(analysis.usage_records)


def test_summary_max_and_grounded_numbers(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    fake = FakeClient([FakeResponse(summary_json())])
    analysis = AnalysisClient(config(), fake)
    result = analysis.summarize(paper(), body())
    assert "0.85" in result.experiments
    assert fake.calls[0][1]["json"]["reasoning_effort"] == "max"
    result.experiments = "留出数据的 Dice 为 0.99。"
    with pytest.raises(ProcessingError, match="number_unverified"):
        validate_summary(result, body())


@pytest.mark.parametrize("task", ["selection", "review", "summary", "translation", "title_translation", "section_notes"])
def test_user_edited_prompt_reaches_the_task_request(tmp_path, monkeypatch, task):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    for path in default_prompt_directory().glob("*.md"):
        (tmp_path / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    target = tmp_path / f"{task}.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nUSER EDIT MARKER", encoding="utf-8")
    cfg = config()
    cfg["prompts"] = {"directory": str(tmp_path)}
    responses = {"selection": decision_json(), "summary": summary_json(),
                 "review": decision_json(review_evidence=[{"field": "method", "locator": "section:Method", "quote": body().sections[0].text, "source_url": body().source_url}]),
                 "translation": {"title_zh": "中文标题", "abstract_zh": "中文完整摘要"},
                 "title_translation": {"title_zh": "中文标题", "abstract_zh": ""}}
    if task == "section_notes":
        cfg = {**config(input_chars=4500), "prompts": cfg["prompts"]}
        b = body()
        for section in b.sections:
            section.text += " Additional text for a long paper. " * 50
        planner = AnalysisClient(cfg, FakeClient([]))
        chunks = planner._chunks(b)
        fake = FakeClient([FakeResponse({"notes": [{"locator": c[0]["locator"], "quote": c[0]["text"][:100], "kind": "other"}]}) for c in chunks])
        analysis = AnalysisClient(cfg, fake)
        analysis._body_context(b)
    else:
        fake = FakeClient([FakeResponse(responses[task])])
        analysis = AnalysisClient(cfg, fake)
        if task == "selection":
            analysis.select(paper(), ["medical_reasoning"])
        elif task == "review":
            analysis.review(paper(), body(), Decision.from_dict(decision_json(status="uncertain", uncertainty=["need method evidence"])))
        elif task == "summary":
            analysis.summarize(paper(), body())
        else:
            analysis.translate(paper(), title_only=task == "title_translation")
    assert fake.calls
    assert all("USER EDIT MARKER" in call[1]["json"]["messages"][0]["content"] for call in fake.calls)


def test_section_prompt_edit_invalidates_cached_evidence(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    b = body()
    for section in b.sections:
        section.text += " Additional text for a long paper. " * 50
    cfg = config(input_chars=4500)
    planner = AnalysisClient(cfg, FakeClient([]))
    chunks = planner._chunks(b)
    responses = [FakeResponse({"notes": [{"locator": c[0]["locator"], "quote": c[0]["text"][:100], "kind": "other"}]}) for c in chunks]
    fake = FakeClient(responses * 2)
    analysis = AnalysisClient(cfg, fake)
    analysis._body_context(b)
    assert len(fake.calls) == len(chunks)
    analysis._body_context(b)
    assert len(fake.calls) == len(chunks)
    analysis.prompts["section_notes"] += "\nA changed extraction requirement"
    analysis._body_context(b)
    assert len(fake.calls) == len(chunks) * 2


def test_summary_rejects_wrong_source_and_unqualified_body():
    data = summary_json()
    data["evidence"][2]["source_url"] = "https://arxiv.org/html/other"
    with pytest.raises(ProcessingError, match="source_mismatch"):
        validate_summary(Summary.from_dict(data), body())
    b = body()
    b.quality["passed"] = False
    with pytest.raises(ProcessingError, match="unqualified"):
        validate_summary(Summary.from_dict(summary_json()), b)


def test_chinese_adjacent_number_and_percentage_are_checked():
    result = Summary.from_dict(summary_json())
    result.experiments = "Dice达到0.99%。"
    with pytest.raises(ProcessingError, match="number_unverified"):
        validate_summary(result, body())


def test_late_appendix_is_read_in_chunked_summary(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    b = body()
    b.sections[0].text = b.sections[0].text + " Method details and constraints. " * 50
    b.sections[1].text = b.sections[1].text + " Evaluation details and metrics. " * 50
    b.sections[2].text = b.sections[2].text + " Appendix details and limits. " * 50
    b.quality["read_locators"] = [s.locator for s in b.sections]
    chunks = AnalysisClient(config(input_chars=4500), FakeClient([]))._chunks(b)
    responses = []
    for chunk in chunks:
        first = chunk[0]
        responses.append(FakeResponse({"notes": [{"locator": first["locator"], "quote": first["text"][:160], "kind": "other"}]}))
    # The final response cites the tail appendix, proving it was available for
    # aggregation instead of being dropped by a prefix cut.
    final = summary_json()
    final["evidence"][0]["quote"] = b.sections[2].text[:80]
    final["evidence"][4]["quote"] = b.sections[2].text[:80]
    responses.append(FakeResponse(final))
    fake = FakeClient(responses)
    analysis = AnalysisClient(config(input_chars=4500), fake)
    result = analysis.summarize(paper(), b)
    assert result.conclusion
    assert len(fake.calls) == len(chunks) + 1
    final_prompt = fake.calls[-1][1]["json"]["messages"][1]["content"]
    assert "section:Appendix" in final_prompt


def test_truncated_json_is_processing_failure(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    fake = FakeClient([FakeResponse(decision_json(), finish="length")])
    analysis = AnalysisClient(config(), fake)
    with pytest.raises(ProcessingError):
        analysis.select(paper(), ["medical mask"])
    assert len(analysis.usage_records) == 1


def test_provider_summary_validation_error_survives_without_raw_content(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    invalid = summary_json()
    invalid["experiments"] = "Dice 为 0.99。"
    fake = FakeClient([FakeResponse(invalid)])
    with pytest.raises(ProcessingError, match="summary_experiments_number_unverified") as failure:
        AnalysisClient(config(), fake).summarize(paper(), body())
    assert "0.99" not in str(failure.value)
    assert "secret-canary" not in str(failure.value)


def test_review_persists_verified_fulltext_evidence(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    prior = Decision.from_dict(decision_json(status="uncertain", route="transferable_objective", uncertainty=["Theory evidence unclear"], theory_evidence=False, transfer_evidence=False))
    result_json = decision_json(status="select", route="transferable_objective", theory_evidence=True, transfer_evidence=True)
    result_json["review_evidence"] = [
        {"field": "theory", "locator": "section:Method", "quote": body().sections[0].text, "source_url": body().source_url},
        {"field": "transfer", "locator": "section:Appendix", "quote": body().sections[2].text, "source_url": body().source_url},
    ]
    fake = FakeClient([FakeResponse(result_json)])
    result = AnalysisClient(config(), fake).review(paper(), body(), prior)
    assert result.review_evidence[0]["locator"] == "section:Method"


def test_longdoc_note_must_come_from_its_actual_chunk(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    b = body()
    bad_quote = "Distinct evidence only in final tail chunk with unique 12345"
    b.sections[0].text += " Other method details. " * 100 + bad_quote
    fake = FakeClient([FakeResponse({"notes": [{"locator": "section:Method", "quote": bad_quote, "kind": "method"}]})])
    analysis = AnalysisClient(config(input_chars=1000), fake)
    with pytest.raises(ProcessingError):
        analysis._body_context(b)
    assert len(analysis.usage_records) == 1


def test_budget_guard_runs_before_model_call(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    fake = FakeClient([])
    analysis = AnalysisClient(config(), fake)
    analysis.run_deadline_monotonic = time.monotonic() - 1
    with pytest.raises(ProcessingError, match="time_guard"):
        analysis.select(paper(), ["medical mask"])
    assert not fake.calls


def test_final_evidence_must_have_been_in_aggregated_prompt(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    b = body()
    for section in b.sections:
        section.text += " Additional grounded detail. " * 50
    probe = AnalysisClient(config(input_chars=4500), FakeClient([]))
    chunks = probe._chunks(b)
    replies = [FakeResponse({"notes": [{"locator": chunk[0]["locator"], "quote": chunk[0]["text"][:30], "kind": "other"}]}) for chunk in chunks]
    replies.append(FakeResponse(summary_json()))
    analysis = AnalysisClient(config(input_chars=4500), FakeClient(replies))
    with pytest.raises(ProcessingError):
        analysis.summarize(paper(), b)
    assert len(analysis.usage_records) == len(chunks) + 1


def test_persisted_chunk_cache_reuses_paid_work_after_failure(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    b = body()
    for section in b.sections:
        section.text += " Additional analysis evidence. " * 60
    cfg = config(input_chars=1500)
    chunks = AnalysisClient(cfg, FakeClient([]))._chunks(b)
    def note(chunk):
        first = chunk[0]
        return {"notes": [{"locator": first["locator"], "quote": first["text"][:80], "kind": "other"}]}
    durable = {}
    first = AnalysisClient(cfg, FakeClient([FakeResponse(note(chunk)) for chunk in chunks]))
    def fail_after_one(key, notes):
        if durable:
            raise PersistenceError("checkpoint_failed")
        durable[key] = deepcopy(notes)
    first.on_chunk = fail_after_one
    with pytest.raises(PersistenceError, match="checkpoint_failed"):
        first._body_context(b)
    assert len(first.client.calls) == 2 and len(durable) == 1

    second = AnalysisClient(cfg, FakeClient([FakeResponse(note(chunk)) for chunk in chunks[1:]]))
    second.chunk_cache = deepcopy(durable)
    second.on_chunk = lambda key, notes: durable.update({key: deepcopy(notes)})
    context = second._body_context(b)
    assert len(second.client.calls) == len(chunks) - 1
    assert len(context["notes"]) == len(chunks)
    assert len(durable) == len(chunks)


def test_usage_checkpoint_failure_never_retries_paid_response(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    cfg = config()
    cfg["llm"]["filter"]["attempts"] = 3
    fake = FakeClient([FakeResponse(decision_json())])
    analysis = AnalysisClient(cfg, fake)
    analysis.on_usage = lambda: (_ for _ in ()).throw(PersistenceError("usage_checkpoint_failed"))
    with pytest.raises(PersistenceError, match="usage_checkpoint_failed"):
        analysis.select(paper(), ["medical mask"])
    assert len(fake.calls) == 1


def test_cost_guard_uses_current_run_cursor_only():
    cfg = config()
    cfg["llm"]["pricing"] = {"cache_hit_per_million": 1, "cache_miss_per_million": 1, "output_per_million": 1}
    cfg["llm"]["max_run_cost"] = 0.1
    analysis = AnalysisClient(cfg, FakeClient([]))
    analysis.usage_records = [{"estimated_cost": 0.5}]
    analysis.usage_start_cursor = 1
    analysis._guard()
    analysis.usage_start_cursor = 0
    with pytest.raises(ProcessingError, match="cost_guard"):
        analysis._guard()


def test_chunk_cache_invalidates_when_model_changes(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    b = body()
    for section in b.sections:
        section.text += " Further study and caveats. " * 55
    cfg = config(input_chars=1500)
    chunks = AnalysisClient(cfg, FakeClient([]))._chunks(b)
    replies = []
    for chunk in chunks:
        item = chunk[0]
        replies.append(FakeResponse({"notes": [{"locator": item["locator"], "quote": item["text"][:80], "kind": "other"}]}))
    first = AnalysisClient(cfg, FakeClient(replies))
    first._body_context(b)
    old_cache = deepcopy(first.chunk_cache)
    changed = deepcopy(cfg)
    changed["llm"]["summary"]["model"] = "another-model"
    second = AnalysisClient(changed, FakeClient(deepcopy(replies)))
    second.chunk_cache = old_cache
    second._body_context(b)
    assert len(second.client.calls) == len(chunks)


def test_malformed_usage_details_and_missing_totals_are_safe(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    cfg = config()
    cfg["llm"]["pricing"] = {"cache_hit_per_million": 1, "cache_miss_per_million": 1, "output_per_million": 1, "policy": "custom"}
    fake = FakeClient([
        FakeResponse(decision_json(), usage={"prompt_tokens": 10, "completion_tokens": 3, "prompt_tokens_details": [], "completion_tokens_details": [], "reasoning_tokens": 2}),
        FakeResponse(decision_json(), usage=None),
    ])
    analysis = AnalysisClient(cfg, fake)
    analysis.select(paper(), [])
    assert analysis.usage_records[0]["usage_available"]
    assert analysis.usage_records[0]["reasoning_tokens"] == 2
    assert analysis.usage_records[0]["pricing_policy"] == "custom"
    analysis.select(paper(), [])
    assert analysis.usage_records[1]["usage_available"] is False
    assert analysis.usage_records[1]["estimated_cost"] is None
    cfg["llm"]["max_run_cost"] = 1
    with pytest.raises(ProcessingError, match="usage_unknown"):
        analysis.select(paper(), [])
    assert len(fake.calls) == 2


def test_wrong_message_type_and_protocol_fail_cleanly(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    fake = FakeClient([FakeResponse(decision_json(), message=["bad"])])
    with pytest.raises(ProcessingError):
        AnalysisClient(config(), fake).select(paper(), [])
    cfg = config()
    cfg["llm"]["filter"]["protocol"] = "responses"
    with pytest.raises(ProcessingError, match="protocol_unsupported"):
        AnalysisClient(cfg, FakeClient([])).select(paper(), [])


def test_httpcore_debug_cannot_emit_authorization_canary(monkeypatch, caplog):
    monkeypatch.setenv("TEST_LLM_KEY", "secret-canary")
    logger = logging.getLogger("httpcore.connection")
    logger.setLevel(logging.DEBUG)
    class DebugClient(FakeClient):
        def post(self, url, **kwargs):
            logger.debug("Authorization: %s", kwargs["headers"]["Authorization"])
            return super().post(url, **kwargs)
    with caplog.at_level(logging.DEBUG):
        AnalysisClient(config(), DebugClient([FakeResponse(decision_json())])).select(paper(), [])
    assert "secret-canary" not in caplog.text


def test_required_figures_on_same_page_share_one_image_input(tmp_path):
    from arxivdaily.models import Figure
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"fixture-image-bytes")
    document = body()
    document.figures = [Figure("Figure 1","pdf-page:2:caption:Figure 1","Architecture figure caption",str(image_path),True),Figure("Table 1","pdf-page:2:caption:Table 1","Quantitative table caption",str(image_path),True)]
    client = AnalysisClient(config(),FakeClient([]))
    assert len(client._images(document)) == 1


def test_summary_cannot_use_only_abstract_quotes_despite_qualified_body():
    document = body()
    abstract = " ".join(s.text for s in document.sections)
    document.sections.insert(0,Section("section:Abstract",abstract))
    data = summary_json()
    for evidence in data["evidence"]:
        evidence["locator"] = "section:Abstract"
    with pytest.raises(ProcessingError,match="abstract_only"):
        validate_summary(Summary.from_dict(data),document)


def test_ambiguous_model_timeout_records_unknown_usage_and_stops_spending_guard(monkeypatch):
    import httpx
    monkeypatch.setenv("TEST_LLM_KEY","secret-canary")
    cfg = config()
    cfg["llm"]["pricing"] = {"cache_hit_per_million":1,"cache_miss_per_million":1,"output_per_million":1,"policy":"custom"}
    cfg["llm"]["max_run_cost"] = 1
    cfg["llm"]["filter"]["attempts"] = 3
    class TimeoutClient:
        calls = 0
        def post(self,*args,**kwargs):
            self.calls += 1
            raise httpx.ReadTimeout("secret-canary")
    fake = TimeoutClient()
    analysis = AnalysisClient(cfg,fake)
    with pytest.raises(ProcessingError,match="usage_unknown"):
        analysis.select(paper(),[])
    assert fake.calls == 1 and not analysis.usage_records[0]["usage_available"]
    assert "secret-canary" not in json.dumps(analysis.usage_records)
