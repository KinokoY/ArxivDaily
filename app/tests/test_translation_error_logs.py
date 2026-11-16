"""Failed translation output remains inspectable without logging successful requests."""
import json

import httpx
import pytest

from arxivdaily.config import load_config
from arxivdaily.llm import AnalysisClient
from arxivdaily.models import ProcessingError
from arxivdaily.translation import TranslationClient
from test_llm import FakeClient, FakeResponse, config, paper


def logs(directory):
    return [json.loads(path.read_text(encoding="utf-8")) for path in directory.glob("translation-*.json")]


@pytest.mark.parametrize("title_only", [False, True])
def test_success_creates_no_log_directory(tmp_path, monkeypatch, title_only):
    monkeypatch.setenv("TEST_LLM_KEY", "test-key")
    directory = tmp_path / "log"
    response = FakeResponse({"title_zh": "中文标题", "abstract_zh": "" if title_only else "中文摘要"})
    client = AnalysisClient(config(), FakeClient([response]), error_log_dir=directory)
    client.translate(paper(), title_only=title_only)
    assert not directory.exists()


@pytest.mark.parametrize("raw,finish,error", [
    ('{"title_zh": "标题", "abstract_zh": ["错误类型"]}', "stop", "translation_schema_invalid"),
    ('{"title_zh": "标题", "abstract_zh": "摘要", "unexpected": 1}', "stop", "translation_schema_invalid"),
    ('{"title_zh": "标题", "abstract_zh": ""}', "stop", "translation_abstract_missing"),
    ('```json\n{"title_zh": "标题"}\n```', "stop", "llm_request_or_response_failed"),
    ('{\n "title_zh": "未完成', "length", "llm_output_incomplete"),
])
def test_failed_original_content_is_preserved_with_paper_and_error(tmp_path, monkeypatch, raw, finish, error):
    monkeypatch.setenv("TEST_LLM_KEY", "test-key")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    directory = tmp_path / "log"
    response = FakeResponse(None, finish=finish, message={"content": raw})
    client = AnalysisClient(config(), FakeClient([response]), error_log_dir=directory)
    with pytest.raises(ProcessingError, match=error):
        client.translate(paper())
    record, = logs(directory)
    assert record["response"]["choices"][0]["message"]["content"] == raw
    assert record["response"]["choices"][0]["finish_reason"] == finish
    assert record["paper_id"] == paper().version_id and record["title"] == paper().title
    assert record["attempt"] == 1 and record["task"] == "translation"
    assert record["error"] == ("JSONDecodeError" if error == "llm_request_or_response_failed" else error)
    assert record["github_run_id"] == "12345"
    assert raw not in json.dumps(client.usage_records, ensure_ascii=False)


def test_failed_retries_keep_separate_logs_even_when_final_request_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "test-key")
    directory = tmp_path / "log"
    cfg = config()
    cfg["llm"]["filter"]["attempts"] = 3
    responses = [FakeResponse({"bad": 1}), FakeResponse({"bad": 2}),
                 FakeResponse({"title_zh": "标题", "abstract_zh": "摘要"})]
    client = AnalysisClient(cfg, FakeClient(responses), error_log_dir=directory)
    assert client.translate(paper()).abstract_zh == "摘要"
    records = sorted(logs(directory), key=lambda r: r["attempt"])
    assert [r["attempt"] for r in records] == [1, 2]
    assert [json.loads(r["response"]["choices"][0]["message"]["content"])["bad"] for r in records] == [1, 2]


def test_title_failure_logs_task_and_removes_credentials_and_reasoning(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TEST_LLM_KEY", "credential-canary")
    monkeypatch.setenv("GITHUB_TOKEN", "github-canary")
    directory = tmp_path / "log"
    response = FakeResponse(None, message={"content": '{"wrong": "credential-canary github-canary"}',
                                          "reasoning_content": "hidden-reasoning-canary"})
    client = AnalysisClient(config(), FakeClient([response]), error_log_dir=directory)
    with pytest.raises(ProcessingError, match="translation_schema_invalid"):
        client.translate(paper(), title_only=True)
    record, = logs(directory)
    assert record["task"] == "title_translation"
    stored = json.dumps(record)
    assert "credential-canary" not in stored and "github-canary" not in stored
    assert "hidden-reasoning-canary" not in stored and "reasoning_content" not in stored
    assert "[REDACTED]" in stored
    assert not capsys.readouterr().out


def test_transport_failure_does_not_log_previous_attempt_response(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "test-key")
    directory = tmp_path / "log"
    cfg = config()
    cfg["llm"]["filter"]["attempts"] = 2
    class Client:
        calls = 0
        def post(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return FakeResponse({"wrong": "first attempt"})
            raise httpx.ConnectError("private-request-canary")
    client = AnalysisClient(cfg, Client(), error_log_dir=directory)
    with pytest.raises(ProcessingError):
        client.translate(paper())
    record, = logs(directory)
    assert record["attempt"] == 1
    assert "private-request-canary" not in json.dumps(record)


@pytest.mark.parametrize("provider", ["deepl", "libretranslate"])
def test_mt_invalid_response_is_logged(tmp_path, monkeypatch, provider):
    cfg = load_config()
    cfg["translation"].update(provider=provider, attempts=1)
    monkeypatch.setenv("TRANSLATION_API_KEY", "mt-canary")
    directory = tmp_path / "log"
    response = {"translations": [{"text": 123}]} if provider == "deepl" else {"translatedText": ["missing abstract"]}
    transport = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)))
    analysis = AnalysisClient(cfg, transport, error_log_dir=directory)
    with pytest.raises(ProcessingError, match="translation_request_failed"):
        TranslationClient(cfg, analysis).translate(paper())
    record, = logs(directory)
    assert record["response"] == response and record["provider"] == provider


def test_log_write_failure_preserves_original_error_and_reports_failure(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("TEST_LLM_KEY", "test-key")
    path = tmp_path / "not-a-directory"
    path.write_text("occupied", encoding="utf-8")
    client = AnalysisClient(config(), FakeClient([FakeResponse({"wrong": "raw-output-canary"})]), error_log_dir=path)
    with pytest.raises(ProcessingError, match="translation_schema_invalid"):
        client.translate(paper())
    assert "translation_error_log_write_failed" in caplog.text
    assert "raw-output-canary" not in caplog.text
