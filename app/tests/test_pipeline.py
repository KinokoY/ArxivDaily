from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from arxivdaily.config import load_config
from arxivdaily.delivery import MockDelivery
from arxivdaily.models import Body, Decision, Evidence, Paper, Section, Summary
from arxivdaily.pipeline import Pipeline
from arxivdaily.simulation import FixtureAnalysis, FixtureReader, load_fixture
from arxivdaily.state import PersistenceError, StateStore

APP = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 2, 7, 17, tzinfo=timezone.utc)


def system(tmp_path, status="confirmed", fixture=None):
    config = load_config()
    config["presentation"].update(abstract=False, abstract_translation=False, llm_summary=True, evidence=False, screening_routes=False)
    f, papers = load_fixture(APP / "fixtures" / "demo.json")
    f = fixture or f
    analysis = FixtureAnalysis(f)
    reader = FixtureReader(config, f, APP / "fixtures" / "demo.json", tmp_path / "raw")
    store = StateStore(tmp_path / "state")
    return config, f, papers, analysis, reader, store, MockDelivery(status)


def test_end_to_end_tiers_and_shared_base_dedup(tmp_path):
    config, f, papers, analysis, reader, store, delivery = system(tmp_path)
    report = Pipeline(config, store, None, analysis, reader, delivery, now=NOW).run(papers + [papers[0]])
    state = store.load()
    assert (report["full"], report["light"]) == (1, 1)
    assert len(state["papers"]) == 4
    assert analysis.calls == {"selection": 4, "review": 1, "summary": 1}
    assert len(delivery.sent) == 1
    md = next((store.directory / "archive/2026/10/02").glob("*.md")).read_text(encoding="utf-8")
    assert "82.5" in md
    light = md.split("## 轻量档")[1].split("\n## ")[0]
    assert "Synthetic fixture 2" in light and "脚本化" not in light
    assert state["papers"][papers[3].base_id]["stage"] == "uncertain"


def test_revision_config_change_does_not_promote_light_or_resummarize(tmp_path):
    config, f, papers, analysis, reader, store, delivery = system(tmp_path)
    Pipeline(config, store, None, analysis, reader, delivery, now=NOW).run(papers[:2])
    p = Paper.from_dict({**papers[1].to_dict(), "version_id": papers[1].base_id + "v2"})
    f["decisions"][p.base_id]["tier"] = "full"
    f["decisions"][p.base_id]["route"] = "medical_reasoning"
    config["llm"]["summary"]["model"] = "changed-model"
    Pipeline(config, store, None, analysis, reader, delivery, now=NOW+timedelta(days=1)).run([p])
    assert analysis.calls["summary"] == 1 and analysis.calls["selection"] == 2
    assert len(delivery.sent) == 2
    assert "今天未发现新增工作" in delivery.sent[1][1]
    assert store.load()["papers"][p.base_id]["intended_tier"] == "light"


def test_unknown_recovery_is_immutable_reuses_summary_capped_across_runs(tmp_path):
    config, f, papers, analysis, reader, store, delivery = system(tmp_path, "unknown")
    reports = []
    for offset in range(4):
        reports.append(Pipeline(config, store, None, analysis, reader, delivery, now=NOW+timedelta(days=offset)).run(papers[:2]))
    state = store.load()
    assert analysis.calls["summary"] == 1
    # Three digest transports, then one merged alert on the fourth day.
    normal = [d for d in state["digests"].values() if not d["alert"]]
    assert len(normal) == 3
    original = normal[0]
    assert state["chains"][original["digest_id"]]["attempts"] == 3
    assert normal[1]["recovery_of"] == [original["digest_id"]]
    assert "补发" in delivery.sent[1][1]
    original_path = store.directory / f"archive/2026/10/02/{original['digest_id']}.md"
    before = original_path.read_bytes()
    Pipeline(config, store, None, analysis, reader, delivery, now=NOW+timedelta(days=4)).run([])
    assert original_path.read_bytes() == before


@pytest.mark.parametrize("count,limit,full,light", [(2,5,2,0),(8,5,5,3),(13,10,10,3)])
def test_full_quota_overflow_is_light_with_no_next_day_summary(tmp_path,count,limit,full,light):
    config, f, papers, analysis, reader, store, delivery = system(tmp_path)
    config["limits"]["full_daily_limit"] = limit
    seed = papers[0]
    many = []
    for index in range(count):
        p = Paper.from_dict({**seed.to_dict(), "version_id": f"2502.{90000+index}v1", "title": f"Synthetic full {index}"})
        many.append(p)
        f["decisions"][p.base_id] = deepcopy(f["decisions"][seed.base_id])
        body = deepcopy(f["bodies"][seed.base_id]); body["version_id"] = p.version_id; body["source_url"] = p.url
        f["bodies"][p.base_id] = body
        s = deepcopy(f["summaries"][seed.base_id])
        for e in s["evidence"]: e["source_url"] = p.url
        f["summaries"][p.base_id] = s
    report = Pipeline(config,store,None,analysis,reader,delivery,now=NOW).run(many)
    assert (report["full"],report["light"]) == (full,light)
    Pipeline(config,store,None,analysis,reader,delivery,now=NOW+timedelta(days=1)).run(many)
    assert analysis.calls["summary"] == full
    assert sum(r.get("tier_reason") == "full_quota_overflow" for r in store.load()["papers"].values()) == light


def test_checkpoint_failure_stops_before_model_and_post(tmp_path):
    config,f,papers,analysis,reader,_,delivery = system(tmp_path)
    def broken(): raise OSError("checkpoint failure")
    store = StateStore(tmp_path/"fail",publisher=broken)
    with pytest.raises(PersistenceError):
        Pipeline(config,store,None,analysis,reader,delivery,now=NOW).run(papers)
    assert analysis.calls["selection"] == 0 and delivery.sent == []


@pytest.mark.parametrize("preferred", ["medical_reasoning", "medical_objective"])
def test_configured_route_priority_controls_the_full_slot(tmp_path, preferred):
    config, f, papers, analysis, reader, store, delivery = system(tmp_path)
    config["limits"]["full_daily_limit"] = 1
    priority = config["selection"]["route_priority"]
    priority.remove(preferred)
    priority.insert(0, preferred)
    seed = papers[0]
    clone = Paper.from_dict({**seed.to_dict(), "version_id": "2502.90001v1", "title": "Another full paper"})
    f["decisions"][clone.base_id] = {**deepcopy(f["decisions"][seed.base_id]), "route": "medical_objective"}
    cloned_body = deepcopy(f["bodies"][seed.base_id])
    cloned_body.update(version_id=clone.version_id, source_url=clone.url)
    f["bodies"][clone.base_id] = cloned_body
    summary = deepcopy(f["summaries"][seed.base_id])
    for evidence in summary["evidence"]:
        evidence["source_url"] = clone.url
    f["summaries"][clone.base_id] = summary
    report = Pipeline(config, store, None, analysis, reader, delivery, now=NOW).run([seed, clone])
    assert not report["errors"] and (report["full"], report["light"]) == (1, 1)
    full = [record for record in store.load()["papers"].values() if record["intended_tier"] == "full"]
    assert full[0]["decision"]["route"] == preferred


def test_secret_canary_and_inflight_unknown_are_publicly_safe(tmp_path):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path,"unknown")
    secret = "".join(chr(x) for x in [99,97,110,97,114,121,45,107,101,121,45,49,50,51])
    store.scrubber.values = [secret]
    f["decisions"][papers[0].base_id]["reason"] += secret
    Pipeline(config,store,None,analysis,reader,delivery,now=NOW).run(papers[:2])
    for p in store.directory.rglob("*"):
        if p.is_file(): assert secret not in p.read_text(encoding="utf-8")
    state = store.load()
    digest_id = next(iter(state["digests"]))
    state["digests"][digest_id]["status"] = "sending"
    store.save(state)
    good = MockDelivery("confirmed")
    Pipeline(config,store,None,analysis,reader,good,now=NOW+timedelta(days=1)).run([])
    assert len(good.sent) == 1 and analysis.calls["summary"] == 1


def test_lock_and_corrupt_state_preserved(tmp_path):
    store = StateStore(tmp_path)
    with store.locked():
        with pytest.raises(PersistenceError):
            with store.locked(): pass
    store.path.write_text("not json",encoding="utf-8")
    with pytest.raises(PersistenceError): store.load()
    assert store.path.read_text() == "not json"


@pytest.mark.parametrize("version",[True,1.0,2])
def test_state_version_is_strict_and_unsupported_file_is_preserved(tmp_path,version):
    from arxivdaily.state import empty_state
    store = StateStore(tmp_path)
    data = empty_state(); data["schema_version"] = version
    raw = json.dumps(data)
    store.path.write_text(raw,encoding="utf-8")
    with pytest.raises(PersistenceError):
        store.load()
    assert store.path.read_text(encoding="utf-8") == raw


def test_failed_promotion_recovers_despite_prior_light_confirmation(tmp_path):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    light = papers[1]
    Pipeline(config,store,None,analysis,reader,delivery,now=NOW).run([light])
    body = deepcopy(f["bodies"][papers[0].base_id]); body["version_id"] = light.version_id; body["source_url"] = light.url
    summary = deepcopy(f["summaries"][papers[0].base_id])
    for e in summary["evidence"]: e["source_url"] = light.url
    f["bodies"][light.base_id] = body; f["summaries"][light.base_id] = summary
    failing = MockDelivery("unknown")
    Pipeline(config,store,None,analysis,reader,failing,now=NOW+timedelta(days=1)).run([],promotion_ids=[light.base_id])
    good = MockDelivery("confirmed")
    report = Pipeline(config,store,None,analysis,reader,good,now=NOW+timedelta(days=2)).run([])
    record = store.load()["papers"][light.base_id]
    assert report["recovery"] == 1 and analysis.calls["summary"] == 1
    assert [e["tier"] for e in record["events"]] == ["light","full","full"]
    assert record["events"][-1]["kind"] == "promotion"


def test_quota_reservation_uses_actual_post_day_across_midnight(tmp_path):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    start = datetime(2026,10,2,15,59,50,tzinfo=timezone.utc)
    post = datetime(2026,10,2,16,0,5,tzinfo=timezone.utc)
    report = Pipeline(config,store,None,analysis,reader,delivery,now=start,clock=lambda:post).run(papers[:2])
    state = store.load()
    assert state["daily"]["2026-10-03"]["send_attempts"] == 1
    assert state["daily"]["2026-10-02"]["send_attempts"] == 0
    assert report["delivery_day"] == "2026-10-03"


def test_daily_send_and_query_budget_do_not_exceed_free_limit(tmp_path):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path,"unknown")
    config["delivery"]["query_counts_quota"] = True
    first = Pipeline(config,store,None,analysis,reader,delivery,now=NOW).run(papers[:2])
    second = Pipeline(config,store,None,analysis,reader,delivery,now=NOW+timedelta(hours=1)).run([])
    ledger = store.load()["daily"]["2026-10-02"]
    assert ledger["send_attempts"] + ledger["query_reservations"] == 4
    assert len(delivery.sent) == 1
    assert "delivery_daily_quota_exhausted" in second["errors"]


def test_collection_checkpoint_independent_of_selection_failure(tmp_path):
    from arxivdaily.collection import CollectionResult
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    class Source:
        def collect(self, window): return CollectionResult(papers=papers[:1],complete=True)
    class Broken(FixtureAnalysis):
        def select(self,paper,hits): raise ValueError("invalid fixture response")
    report = Pipeline(config,store,Source(),Broken(f),reader,delivery,now=NOW).run()
    state = store.load()
    assert state["collection"]["last_complete_end"] == NOW.isoformat()
    assert "decision" not in state["papers"][papers[0].base_id]
    assert report["errors"] and state["papers"][papers[0].base_id]["stage"] == "candidate"


def test_incomplete_collection_does_not_advance_complete_cursor(tmp_path):
    from arxivdaily.collection import CollectionResult
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    class Source:
        def collect(self,window): return CollectionResult(papers=papers[:2],complete=False,shards=[{"status":"interrupted"}],errors=["page_interrupted"])
    report = Pipeline(config,store,Source(),analysis,reader,delivery,now=NOW).run()
    state = store.load()
    assert "last_complete_end" not in state["collection"]
    assert report["full"] == 1 and "collection_incomplete" in report["errors"]


def test_post_confirmation_checkpoint_loss_retains_unknown_and_attempt(tmp_path):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    remote = {}
    def publisher():
        current = store.load()
        if any(d["status"] == "confirmed" for d in current["digests"].values()):
            raise OSError("result publish failed")
        remote.clear(); remote.update(deepcopy(current))
    store.publisher = publisher
    with pytest.raises(PersistenceError):
        Pipeline(config,store,None,analysis,reader,delivery,now=NOW).run(papers[:2])
    assert len(delivery.sent) == 1
    store.publisher = None
    store.save(remote)  # A fresh runner receives the last published checkpoint.
    good = MockDelivery("confirmed")
    report = Pipeline(config,store,None,analysis,reader,good,now=NOW+timedelta(days=1)).run([])
    assert report["recovery"] == 2 and len(good.sent) == 1
    assert analysis.calls["summary"] == 1
    original = next(iter(remote["chains"]))
    assert store.load()["chains"][original]["attempts"] == 2


def test_existing_stage_failure_is_not_reported_as_silent_empty(tmp_path):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    class Broken(FixtureAnalysis):
        def select(self,paper,hits): raise ValueError("malformed response")
    broken = Broken(f)
    Pipeline(config,store,None,broken,reader,delivery,now=NOW).run(papers[:1])
    report = Pipeline(config,store,None,broken,reader,delivery,now=NOW+timedelta(hours=1)).run([])
    assert not report["silent"]
    assert any("recovery_deferred_after_failure" in e for e in report["errors"])
    assert store.load()["papers"][papers[0].base_id]["attempts"]["selection"] == 1


def test_unexpected_collector_failure_preserves_incomplete_run_and_alert(tmp_path):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    class BrokenSource:
        def collect(self,window): raise ValueError("bad feed")
    report = Pipeline(config,store,BrokenSource(),analysis,reader,delivery,now=NOW).run()
    assert not report["coverage_complete"] and not report["silent"]
    assert "last_complete_end" not in store.load()["collection"]
    assert len(delivery.sent) == 1


@pytest.mark.parametrize("transition_stage", ["prepared", "sending"])
def test_publisher_crossing_midnight_defers_without_post_or_quota_use(tmp_path,transition_stage):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    start = datetime(2026,10,2,15,59,50,tzinfo=timezone.utc)
    after = datetime(2026,10,2,16,0,5,tzinfo=timezone.utc)
    clock_value = [start]
    def publish():
        if any(d["status"] == transition_stage for d in store.load()["digests"].values()):
            clock_value[0] = after
    store.publisher = publish
    report = Pipeline(config,store,None,analysis,reader,delivery,now=start,clock=lambda:clock_value[0]).run(papers[:2])
    assert not delivery.sent
    assert any("day_changed_during" in e for e in report["errors"])
    state = store.load()
    assert all(d["send_attempts"] == 0 for d in state["daily"].values())
    assert all(c["attempts"] == 0 for c in state["chains"].values())
    assert all(not r.get("pending_digest") for r in state["papers"].values())
    store.publisher = None
    report = Pipeline(config,store,None,analysis,reader,delivery,now=after).run([])
    assert len(delivery.sent) == 1 and analysis.calls["summary"] == 1


def test_unknown_provider_usage_stops_configured_spending_guard(tmp_path):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    config["llm"]["max_run_cost"] = 1
    class UnknownUsage(FixtureAnalysis):
        def select(self,paper,hits):
            self.usage_records.append({"usage_available":False,"estimated_cost":None})
            return super().select(paper,hits)
    unknown = UnknownUsage(f)
    report = Pipeline(config,store,None,unknown,reader,delivery,now=NOW).run(papers[:2])
    assert unknown.calls["selection"] == 1 and unknown.calls["summary"] == 0
    assert "run_cost_guard_usage_unknown" in report["errors"]


def test_manual_delivery_recovery_preserves_total_attempts_and_targets_only_requested_ids(tmp_path):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path,"unknown")
    for offset in range(3):
        Pipeline(config,store,None,analysis,reader,delivery,now=NOW+timedelta(days=offset)).run(papers[:2])
    before = store.load()
    original_chain = before["papers"][papers[0].base_id]["delivery_chain"]
    good = MockDelivery("confirmed")
    report = Pipeline(config,store,None,analysis,reader,good,now=NOW+timedelta(days=20)).run([],retry_stage="delivery",retry_ids=[papers[0].base_id])
    after = store.load()
    assert report["full"] == 1 and report["light"] == 0 and report["recovery"] == 1
    assert after["chains"][original_chain]["attempts"] == 4
    assert after["papers"][papers[1].base_id]["pending_digest"] == before["papers"][papers[1].base_id]["pending_digest"]
    assert analysis.calls["summary"] == 1
    assert after["papers"][papers[0].base_id]["first_discovered"] == before["papers"][papers[0].base_id]["first_discovered"]


def test_manual_stage_retry_restores_only_failed_stage_after_expiry(tmp_path):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    class Broken(FixtureAnalysis):
        def select(self,paper,hits): raise ValueError("bad response")
    Pipeline(config,store,None,Broken(f),reader,delivery,now=NOW).run(papers[:1])
    before = store.load()["papers"][papers[0].base_id]["first_discovered"]
    report = Pipeline(config,store,None,analysis,reader,delivery,now=NOW+timedelta(days=20)).run([],retry_stage="selection",retry_ids=[papers[0].base_id])
    record = store.load()["papers"][papers[0].base_id]
    assert report["full"] == 1 and not report["errors"]
    assert record["first_discovered"] == before
    assert record["manual_retry_events"][0]["prior_attempts"]["selection"] == 1
    assert record["attempts"]["selection"] == 1


def test_confirmed_full_requires_explicit_resend_not_promotion(tmp_path):
    from arxivdaily.models import ProcessingError
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    Pipeline(config,store,None,analysis,reader,delivery,now=NOW).run(papers[:1])
    with pytest.raises(ProcessingError,match="confirmed_light_only"):
        Pipeline(config,store,None,analysis,reader,delivery,now=NOW).run([],promotion_ids=[papers[0].base_id])
    result = Pipeline(config,store,None,analysis,reader,delivery,now=NOW).run([],resend_ids=[papers[0].base_id])
    assert result["full"] == 1 and len(delivery.sent) == 2
    assert analysis.calls["summary"] == 1
    assert store.load()["papers"][papers[0].base_id]["events"][-1]["kind"] == "resend"


def test_manual_review_reuses_same_day_paper_slot(tmp_path):
    config,f,papers,analysis,reader,store,delivery = system(tmp_path)
    uncertain = papers[3]
    Pipeline(config,store,None,analysis,reader,delivery,now=NOW).run([uncertain])
    report = Pipeline(config,store,None,analysis,reader,delivery,now=NOW+timedelta(hours=1)).run([],retry_stage="review",retry_ids=[uncertain.base_id])
    assert analysis.calls["review"] == 2
    assert store.load()["daily"]["2026-10-02"]["review_ids"] == [uncertain.base_id]
