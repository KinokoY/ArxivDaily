from copy import deepcopy
from datetime import timedelta
import json

import httpx
import pytest

from arxivdaily.feedback import (Feedback, FeedbackError, GitHubFeedbackClient,
                                issue_marker, parse_votes, tally_feedback)
from arxivdaily.models import DigestItem, Paper, Translation
from arxivdaily.pipeline import Pipeline
from arxivdaily.rules import match_rules, trace_rules
from arxivdaily.render import markdown_text, render_item, render_notification
from arxivdaily.state import PersistenceError, StateStore, empty_state
from test_pipeline import NOW, system


class GitHub:
    repository = "owner/repo"

    def __init__(self):
        self.issues = {}
        self.created = self.updated = self.deleted = self.closed = 0
        self.delete_error = False
        self.on_delete = lambda: None
        self.on_close = lambda: None

    def get(self, number):
        return deepcopy(self.issues.get(number))

    def find(self, marker):
        return next((deepcopy(r) for r in self.issues.values() if marker in r["body"]), None)

    def create(self, title, body):
        self.created += 1
        number = self.created
        self.issues[number] = dict(number=number, node_id=f"I_{number}", title=title, body=body, state="open")
        return self.get(number)

    def update(self, number, body):
        self.updated += 1
        self.issues[number]["body"] = body
        return self.get(number)

    def delete(self, node_id):
        self.on_delete()
        if self.delete_error:
            raise FeedbackError("feedback_delete_token_missing")
        self.deleted += 1
        number = next(n for n, row in self.issues.items() if row["node_id"] == node_id)
        del self.issues[number]

    def close(self, number):
        self.on_close()
        self.closed += 1
        self.issues[number]["state"] = "closed"
        return self.get(number)

    def vote(self, key, value, number=1):
        for vote, label in (("like", "👍 对我有用"), ("dislike", "👎 对我无用")):
            old = f"- [ ] {label} <!-- vote:{key}:{vote} -->"
            checked = old.replace("[ ]", "[x]")
            body = self.issues[number]["body"].replace(checked, old)
            self.issues[number]["body"] = body.replace(old, checked) if value in (vote, "conflict") else body


def setup(tmp_path, count=2):
    cfg, fixture, papers, analysis, reader, store, delivery = system(tmp_path)
    cfg["feedback"]["cleanup_action"] = "delete"  # Exercise the optional permanent-delete path.
    items = [DigestItem(p, "translation", translation=Translation("中文标题 " + p.base_id),
                       modules=["title", "screening_routes"], rule_hits=match_rules(p, cfg),
                       rule_trace=trace_rules(p, cfg)) for p in papers[:count]]
    github = GitHub()
    manager = Feedback(cfg["feedback"], github)
    state = empty_state()
    return cfg, items, github, manager, state, store


def test_daily_issue_bilingual_links_append_preserves_votes_and_retry(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    save = lambda: store.save(state)
    url = manager.ensure_daily(state, "2026-10-02", items[:1], NOW, save)
    gh.vote(items[0].paper.base_id, "like")
    manager.ensure_daily(state, "2026-10-02", items, NOW, save)
    manager.ensure_daily(state, "2026-10-02", items, NOW, save)
    assert url == "https://github.com/owner/repo/issues/1"
    assert gh.created == 1 and gh.updated == 1
    body = gh.issues[1]["body"]
    for item in items:
        assert markdown_text(item.paper.title) in body and item.translation.title_zh in body and item.paper.url in body
    assert parse_votes(body, [items[0].paper.base_id])[items[0].paper.base_id] == "like"


def test_creation_recovered_after_remote_success_but_checkpoint_failure(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    def save():
        if gh.created:
            raise PersistenceError("failed publication")
        store.save(state)
    with pytest.raises(PersistenceError):
        manager.ensure_daily(state, "2026-10-02", items, NOW, save)
    state = store.load()  # No remote number was durable, recover using exact marker.
    manager.ensure_daily(state, "2026-10-02", items, NOW, lambda: store.save(state))
    assert gh.created == 1 and state["feedback"]["issues"]["2026-10-02"]["number"] == 1


def test_failed_creation_is_retried_from_saved_snapshot_next_run(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    create = gh.create
    def fail(*args):
        raise FeedbackError("github unavailable")
    gh.create = fail
    with pytest.raises(FeedbackError):
        manager.ensure_daily(state, "2026-10-02", items, NOW, lambda: store.save(state))
    gh.create = create
    state = store.load()
    assert manager.sync(state, NOW + timedelta(days=1), "2026-10-03", lambda: store.save(state)) == []
    assert gh.created == 1 and not gh.deleted
    assert state["feedback"]["issues"]["2026-10-02"]["url"].endswith("/issues/1")


def test_failed_append_is_recovered_without_erasing_existing_votes(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    save = lambda: store.save(state)
    manager.ensure_daily(state, "2026-10-02", items[:1], NOW, save)
    gh.vote(items[0].paper.base_id, "like")
    update = gh.update
    def fail(*args):
        raise FeedbackError("github unavailable")
    gh.update = fail
    with pytest.raises(FeedbackError):
        manager.ensure_daily(state, "2026-10-02", items, NOW, save)
    gh.update = update
    state = store.load()
    manager.sync(state, NOW + timedelta(days=1), "2026-10-03", lambda: store.save(state))
    assert parse_votes(gh.issues[1]["body"], [i.paper.base_id for i in items]) == {
        items[0].paper.base_id: "like", items[1].paper.base_id: "pending"}
    assert gh.created == 1 and not gh.deleted


def test_counts_are_keyword_specific_votes_can_change_and_retries_do_not_add(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    save = lambda: store.save(state)
    manager.ensure_daily(state, "2026-10-02", items, NOW, save)
    key = items[0].paper.base_id
    gh.vote(key, "like")
    for _ in range(2):
        assert manager.sync(state, NOW, "2026-10-02", save) == []
    counts = state["feedback"]["counts"]
    assert counts["rated_papers"] == 1
    assert all(r["like"] == 1 and r["dislike"] == 0 for r in counts["keywords"])
    expected = {(c["route"], group, hit["keyword"]) for c in items[0].rule_trace["clauses"]
                for group, hits in c["keywords"].items() for hit in hits}
    assert {(r["route"], r["group"], r["keyword"]) for r in counts["keywords"]} == expected
    cfg["rules"]["groups"]["MED"] = ["changed"]
    gh.vote(key, "dislike")
    manager.sync(state, NOW, "2026-10-02", save)
    assert all(r["like"] == 0 and r["dislike"] == 1 for r in state["feedback"]["counts"]["keywords"])
    assert state["feedback"]["issues"]["2026-10-02"]["papers"][key]["rule_trace"] == items[0].rule_trace
    for value in ("conflict", "pending"):
        gh.vote(key, value)
        manager.sync(state, NOW, "2026-10-02", save)
        assert state["feedback"]["counts"]["rated_papers"] == 0
    assert (store.directory / "archive/feedback.md").is_file()


def test_complete_issue_published_before_deletion_and_today_is_retained(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    published = []
    def save():
        store.save(state)
        published.append(deepcopy(state))
    manager.ensure_daily(state, "2026-10-02", items, NOW, save)
    for item in items:
        gh.vote(item.paper.base_id, "like")
    manager.sync(state, NOW, "2026-10-02", save)
    assert not gh.deleted
    def deletion_check():
        entry = published[-1]["feedback"]["issues"]["2026-10-02"]
        assert entry["cleanup_pending"] == "complete"
        assert all(r["vote"] == "like" for r in entry["papers"].values())
    gh.on_delete = deletion_check
    manager.sync(state, NOW + timedelta(days=1), "2026-10-03", save)
    manager.sync(state, NOW + timedelta(days=2), "2026-10-04", save)
    assert gh.deleted == 1 and state["feedback"]["counts"]["rated_papers"] == 2


def test_expiry_reads_final_votes_and_unreviewed_papers_are_not_dislikes(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    save = lambda: store.save(state)
    manager.ensure_daily(state, "2026-10-02", items, NOW, save)
    gh.vote(items[0].paper.base_id, "dislike")
    manager.sync(state, NOW + timedelta(days=14), "2026-10-16", save)
    assert gh.deleted == 1
    entry = state["feedback"]["issues"]["2026-10-02"]
    assert entry["cleanup_pending"] == "expired"
    assert entry["papers"][items[1].paper.base_id]["vote"] == "pending"
    assert state["feedback"]["counts"]["rated_papers"] == 1


def test_publish_failure_prevents_delete_and_delete_failure_keeps_saved_votes(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    save = lambda: store.save(state)
    manager.ensure_daily(state, "2026-10-02", items, NOW, save)
    for item in items:
        gh.vote(item.paper.base_id, "like")
    def fail():
        raise PersistenceError("publication failed")
    with pytest.raises(PersistenceError):
        manager.sync(state, NOW + timedelta(days=1), "2026-10-03", fail)
    assert gh.deleted == 0
    gh.delete_error = True
    errors = manager.sync(state, NOW + timedelta(days=1), "2026-10-03", save)
    assert "feedback_delete_token_missing" in errors[0]
    assert store.load()["feedback"]["counts"]["rated_papers"] == 2
    gh.delete_error = False
    manager.sync(state, NOW + timedelta(days=2), "2026-10-04", save)
    assert gh.deleted == 1


def test_delete_success_checkpoint_failure_recovers_missing_issue(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    manager.ensure_daily(state, "2026-10-02", items, NOW, lambda: store.save(state))
    for item in items:
        gh.vote(item.paper.base_id, "like")
    def save():
        if gh.deleted:
            raise PersistenceError("publication failed")
        store.save(state)
    with pytest.raises(PersistenceError):
        manager.sync(state, NOW + timedelta(days=1), "2026-10-03", save)
    state = store.load()
    assert manager.sync(state, NOW + timedelta(days=2), "2026-10-04", lambda: store.save(state)) == []
    assert state["feedback"]["issues"]["2026-10-02"]["status"] == "deleted"
    assert gh.deleted == 1


def test_changed_body_during_publish_is_not_deleted(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    manager.ensure_daily(state, "2026-10-02", items, NOW, lambda: store.save(state))
    for item in items:
        gh.vote(item.paper.base_id, "like")
    def save():
        store.save(state)
        gh.vote(items[0].paper.base_id, "dislike")
    manager.sync(state, NOW + timedelta(days=1), "2026-10-03", save)
    assert gh.deleted == 0


def test_missing_or_duplicate_checkbox_is_invalid_and_cannot_complete_issue(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    save = lambda: store.save(state)
    manager.ensure_daily(state, "2026-10-02", items[:1], NOW, save)
    key = items[0].paper.base_id
    gh.vote(key, "like")
    gh.issues[1]["body"] += f"\n- [x] duplicate <!-- vote:{key}:like -->\n"
    manager.sync(state, NOW + timedelta(days=1), "2026-10-03", save)
    assert gh.deleted == 0 and state["feedback"]["counts"]["rated_papers"] == 0


def test_duplicate_paper_in_resend_counts_once(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    save = lambda: store.save(state)
    manager.ensure_daily(state, "2026-10-02", items, NOW, save)
    gh.vote(items[0].paper.base_id, "like")
    manager.sync(state, NOW, "2026-10-02", save)
    manager.ensure_daily(state, "2026-10-03", items, NOW + timedelta(days=1), save)
    gh.vote(items[0].paper.base_id, "dislike", number=2)
    manager.sync(state, NOW + timedelta(days=1), "2026-10-03", save)
    assert state["feedback"]["counts"]["rated_papers"] == 1
    assert all(row["like"] == 0 and row["dislike"] == 1 for row in state["feedback"]["counts"]["keywords"])


def test_http_client_uses_owner_token_only_for_deletion_and_redacts_failures(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ordinary-secret")
    monkeypatch.setenv("FEEDBACK_DELETE_TOKEN", "owner-secret")
    calls = []
    def handle(request):
        calls.append(request)
        if request.url.path == "/graphql":
            return httpx.Response(200, json={"errors": [{"message": "owner-secret"}]})
        return httpx.Response(200, json={"number": 1})
    client = GitHubFeedbackClient(dict(repository="owner/repo", token_env="GITHUB_TOKEN", delete_token_env="FEEDBACK_DELETE_TOKEN"),
                                  httpx.Client(transport=httpx.MockTransport(handle)))
    client.get(1)
    with pytest.raises(FeedbackError, match="permission") as exc:
        client.delete("I_1")
    assert "owner-secret" not in str(exc.value)
    assert calls[0].headers["Authorization"] == "Bearer ordinary-secret"
    assert calls[1].headers["Authorization"] == "Bearer owner-secret"
    assert json.loads(calls[1].content)["variables"] == {"id": "I_1"}


def test_pipeline_connects_feedback_link_trace_and_titles(tmp_path):
    cfg, fixture, papers, analysis, reader, store, delivery = system(tmp_path)
    cfg["presentation"] = {key: key in ("title", "source", "screening_routes") for key in cfg["presentation"]}
    cfg["archive"]["public_base_url"] = "https://example.org/state"
    store.publisher = lambda: None
    gh = GitHub()
    manager = Feedback(cfg["feedback"], gh)
    result = Pipeline(cfg, store, None, analysis, reader, delivery, now=NOW, real_send=True, feedback=manager).run(papers[:1])
    assert result["errors"] == []
    assert "反馈今日论文" in delivery.sent[0][1]
    assert "https://github.com/owner/repo/issues/1" in delivery.sent[0][1]
    assert "命中关键词" in delivery.sent[0][1]
    assert gh.created == 1 and analysis.translation_calls
    state = store.load()
    manifest = state["digests"][result["digest_id"]]
    assert manifest["feedback_url"] and manifest["items"][0]["rule_trace"]["source"] == "matched"
    trace = deepcopy(manifest["items"][0]["rule_trace"])
    cfg["rules"]["groups"]["MED"] = ["different"]
    assert Pipeline._item(state["papers"][papers[0].base_id]).rule_trace == trace


def test_offline_pipeline_never_uses_feedback_client(tmp_path):
    cfg, fixture, papers, analysis, reader, store, delivery = system(tmp_path)
    class Forbidden:
        def sync(self, *args):
            pytest.fail("dry run contacted GitHub")
    Pipeline(cfg, store, None, analysis, reader, delivery, now=NOW, feedback=Forbidden()).run(papers[:1])
    assert "feedback" not in store.load()


def test_precise_trace_title_abstract_and_failed_clauses(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    cfg["rules"] = {"title_enabled": True, "categories": [], "exclude": [],
        "groups": {"A": ["medical", "CT"], "B": ["segmentation", "segment"], "C": ["absent"]},
        "routes": {"one": [["A", "B"], ["A", "C"]], "two": [["A", "B"]]}}
    p = Paper.from_dict({**items[0].paper.to_dict(), "title": "Medical segmentation",
                        "abstract": "Medical CT segmentation with activities."})
    trace = trace_rules(p, cfg)
    assert len(trace["clauses"]) == 2
    assert trace["clauses"][0]["keywords"]["A"] == [
        {"keyword": "medical", "fields": ["abstract", "title"]}, {"keyword": "CT", "fields": ["abstract"]}]
    assert trace["clauses"][0]["keywords"]["B"] == [{"keyword": "segmentation", "fields": ["abstract", "title"]}]
    item = DigestItem(p, "translation", modules=["screening_routes"], rule_hits=["one", "two"], rule_trace=trace)
    rendered = render_item(item)
    assert "medical（摘要、标题）" in rendered and "CT（摘要）" in rendered
    assert "absent" not in rendered and "segment（" not in rendered
    cfg["rules"]["title_enabled"] = False
    assert trace_rules(p, cfg)["clauses"][0]["keywords"]["A"][0]["fields"] == ["abstract"]
    cfg["rules"]["exclude"] = ["CT"]
    assert trace_rules(p, cfg)["clauses"] == []


def test_phrase_does_not_match_across_abstract_title_boundary(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    cfg["rules"] = {"title_enabled": True, "categories": [], "exclude": [],
                    "groups": {"A": ["spatial reasoning"]}, "routes": {"route": [["A"]]}}
    p = Paper.from_dict({**items[0].paper.to_dict(), "abstract": "We study spatial", "title": "reasoning methods"})
    assert match_rules(p, cfg) == [] and trace_rules(p, cfg)["clauses"] == []


def test_client_recovers_only_our_issue_and_follows_pagination(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-secret")
    marker = issue_marker("2026-10-02")
    def handle(request):
        page = request.url.params["page"]
        if page == "1":
            return httpx.Response(200, json=[{"body": marker, "user": {"login": "outsider"}}] * 100)
        return httpx.Response(200, json=[{"body": marker, "user": {"login": "github-actions[bot]"}, "number": 7}])
    client = GitHubFeedbackClient(dict(repository="owner/repo", token_env="GITHUB_TOKEN", delete_token_env="FEEDBACK_DELETE_TOKEN"),
                                  httpx.Client(transport=httpx.MockTransport(handle)))
    assert client.find(marker)["number"] == 7


def test_feedback_url_survives_notification_size_trimming(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    item = items[0]
    item.modules = ["abstract_translation", "screening_routes"]
    item.translation.abstract_zh = "很长的摘要" * 1000
    body, modes = render_notification("2026-10-02", [item], "https://example.org/a.md", 500,
                                      feedback_url="https://github.com/owner/repo/issues/1")
    assert len(body.encode()) <= 500
    assert "https://github.com/owner/repo/issues/1" in body
    assert modes[item.paper.base_id] == "translation_archive_link_only"


@pytest.mark.parametrize("value", ['enabled = 1', 'max_wait_days = 0', 'repository = "https://github.com/a/b"', 'token_env = "literal token"', 'cleanup_action = "archive"'])
def test_invalid_feedback_configuration_is_rejected(tmp_path, value):
    from arxivdaily.config import load_config
    path = tmp_path / "config.toml"
    path.write_text("[feedback]\n" + value, encoding="utf-8")
    with pytest.raises(ValueError, match="feedback"):
        load_config(path)


@pytest.mark.parametrize("action", ["close", "delete"])
def test_two_of_three_votes_saved_next_run_without_waiting_for_completion(tmp_path, action):
    cfg, items, gh, manager, state, store = setup(tmp_path, count=3)
    cfg["feedback"]["cleanup_action"] = action
    save = lambda: store.save(state)
    manager.ensure_daily(state, "2026-10-02", items, NOW, save)
    gh.vote(items[0].paper.base_id, "like")
    gh.vote(items[1].paper.base_id, "dislike")
    assert manager.sync(state, NOW + timedelta(days=1), "2026-10-03", save) == []
    persisted = store.load()["feedback"]
    assert persisted["counts"]["rated_papers"] == 2
    entry = persisted["issues"]["2026-10-02"]
    assert entry["papers"][items[2].paper.base_id]["vote"] == "pending"
    assert entry["status"] == "open" and not gh.closed and not gh.deleted
    assert "已评价论文：2 篇" in (store.directory / "archive/feedback.md").read_text(encoding="utf-8")
    manager.sync(state, NOW + timedelta(days=13), "2026-10-15", save)
    assert not gh.closed and not gh.deleted
    manager.sync(state, NOW + timedelta(days=14), "2026-10-16", save)
    persisted = store.load()["feedback"]
    assert persisted["counts"]["rated_papers"] == 2
    assert persisted["issues"]["2026-10-02"]["status"] == ("closed" if action == "close" else "deleted")
    assert gh.closed == (action == "close") and gh.deleted == (action == "delete")


def test_close_requires_published_votes_and_recovers_interrupted_checkpoint(tmp_path):
    cfg, items, gh, manager, state, store = setup(tmp_path)
    cfg["feedback"]["cleanup_action"] = "close"
    manager.ensure_daily(state, "2026-10-02", items, NOW, lambda: store.save(state))
    for item in items:
        gh.vote(item.paper.base_id, "like")
    def fail():
        raise PersistenceError("publication failed")
    with pytest.raises(PersistenceError):
        manager.sync(state, NOW + timedelta(days=1), "2026-10-03", fail)
    assert gh.closed == 0
    def check_before_close():
        entry = store.load()["feedback"]["issues"]["2026-10-02"]
        assert entry["cleanup_action"] == "close"
        assert all(row["vote"] == "like" for row in entry["papers"].values())
    gh.on_close = check_before_close
    def interrupted():
        if gh.closed:
            raise PersistenceError("publication failed after closing")
        store.save(state)
    with pytest.raises(PersistenceError):
        manager.sync(state, NOW + timedelta(days=1), "2026-10-03", interrupted)
    state = store.load()
    assert gh.issues[1]["state"] == "closed" and gh.closed == 1
    manager.sync(state, NOW + timedelta(days=2), "2026-10-04", lambda: store.save(state))
    assert gh.closed == 1 and not gh.deleted
    assert store.load()["feedback"]["issues"]["2026-10-02"]["status"] == "closed"
    manager.sync(state, NOW + timedelta(days=3), "2026-10-05", lambda: store.save(state))
    assert gh.closed == 1


def test_default_cleanup_is_close_and_needs_no_deletion_token(monkeypatch):
    from arxivdaily.config import load_config, default_config_path
    assert load_config()["feedback"]["cleanup_action"] == "close"
    settings = load_config(default_config_path())["feedback"]
    assert settings["cleanup_action"] == "close"
    settings["repository"] = "owner/repo"
    monkeypatch.setenv("GITHUB_TOKEN", "normal-token")
    monkeypatch.delenv("FEEDBACK_DELETE_TOKEN", raising=False)
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"number": 1, "state": "closed"})
    client = GitHubFeedbackClient(settings, httpx.Client(transport=httpx.MockTransport(handle)))
    assert client.close(1)["state"] == "closed"
    assert calls[0].method == "PATCH" and calls[0].url.path == "/repos/owner/repo/issues/1"
    assert calls[0].headers["Authorization"] == "Bearer normal-token"
    assert json.loads(calls[0].content) == {"state": "closed"}
