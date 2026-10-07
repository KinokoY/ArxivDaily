"""Bounded, cached DeepSeek smoke check on existing fixed paper sources.

Uses DEEPSEEK_API_KEY from the environment. Never sends a notification or
updates production state. Successful stages are reused; failed/started stages
require --retry-failed before another paid attempt. Default: two filters and
one fulltext+image summary, one transport attempt per request.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

import httpx

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from arxivdaily.config import load_config
from arxivdaily.llm import AnalysisClient, validate_summary
from arxivdaily.prompts import load_prompts
from arxivdaily.models import Decision, DigestItem, Paper, ProcessingError, Summary, fingerprint
from arxivdaily.render import render_archive
from arxivdaily.rules import match_rules
from arxivdaily.simulation import FixtureReader
from arxivdaily.state import SecretScrubber


class ObservedClient(httpx.Client):
    """Keep only HTTP status and completion state, never provider text."""
    def __init__(self):
        super().__init__()
        self.observations = []
        self.visible_outputs = []

    def post(self, *args, **kwargs):
        event = {"http_status": None, "finish_reason": None}
        self.observations.append(event)
        response = super().post(*args, **kwargs)
        event["http_status"] = response.status_code
        if response.is_success:
            try:
                reason = response.json()["choices"][0]["finish_reason"]
                if reason in {"stop", "length", "content_filter", "tool_calls", "insufficient_system_resource", "aborted"}:
                    event["finish_reason"] = reason
                content = response.json()["choices"][0]["message"]["content"]
                value = json.loads(content)
                if isinstance(value, dict):
                    self.visible_outputs.append(value)
            except (ValueError, KeyError, IndexError, TypeError):
                pass
        return response


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["all", "selection", "summary"], default="all")
    parser.add_argument("--prepare-only", action="store_true", help="parse/hash local sources without paid requests")
    parser.add_argument("--retry-failed", action="store_true", help="explicitly allow one more attempt at a failed/started stage")
    parser.add_argument("--refresh-summary", action="store_true", help="explicit new summary after a prompt/parser change; preserve the previous result")
    args = parser.parse_args()
    config = load_config(APP.parent / "config.toml")
    for role in ("filter", "summary"):
        config["llm"][role]["attempts"] = 1
    fixture_path = APP / "fixtures" / "representative.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    reader = FixtureReader(config, fixture, fixture_path, APP / "tmp" / "live-api")
    papers = {p.base_id: p for p in map(Paper.from_dict, fixture["papers"])}
    body = reader.read(papers["2504.11008"])
    if not body.qualified:
        raise ProcessingError("local_fulltext_gate_failed")
    public_body = {
        "version_id": body.version_id, "source_url": body.source_url,
        "source_type": body.source_type, "qualified": body.qualified,
        "read_chars": body.quality["read_chars"], "section_count": len(body.sections),
        "rendered_physical_pages": body.quality.get("rendered_physical_pages", []),
        "required_images": len({f.image_path for f in body.figures if f.required}),
    }
    # Source/hash checks run even when reusing validated results.
    key = fingerprint({"script_contract": 2, "source_manifest": fixture["source_manifest_sha256"], "llm": config["llm"], "prompts": load_prompts(config)})
    path = APP / "tmp" / "tools" / "live-api" / key / "report.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {
        "kind": "real_deepseek_small_smoke", "contract_fingerprint": key,
        "notification_requests": 0, "production_state_changed": False,
        "stages": {}, "usage": [], "observations": [],
    }
    if report.get("contract_fingerprint") != key:
        raise ProcessingError("smoke_contract_changed_preserve_existing_report")
    report["fulltext"] = public_body
    if args.prepare_only:
        print(json.dumps(public_body, ensure_ascii=False))
        return 0
    credential_names = {config["llm"][role]["api_key_env"] for role in ("filter", "summary")}
    if any(not os.environ.get(name) for name in credential_names):
        raise ProcessingError("llm_key_missing")
    scrubber = SecretScrubber([os.environ.get(name, "") for name in credential_names | {config["delivery"]["sendkey_env"]}])
    client = ObservedClient()
    analysis = AnalysisClient(config, client=client)

    def save():
        report["updated_at"] = datetime.now(timezone.utc).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / "report.atomic.json"
        temporary.write_text(json.dumps(scrubber.clean(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)

    def stage(name, operation):
        old = report["stages"].get(name, {})
        refresh = name.startswith("summary:") and args.refresh_summary
        if old.get("status") == "validated" and not refresh:
            print(f"{name}: reused validated result", flush=True)
            return True
        if old and not (args.retry_failed or refresh):
            print(f"{name}: previous attempt preserved; use --retry-failed for another paid request", flush=True)
            return False
        history = list(old.get("history", []))
        if old:
            history.append({k: v for k, v in old.items() if k != "history"})
        report["stages"][name] = {"status": "started", "attempts": old.get("attempts", 0) + 1, "history": history}
        if name.startswith("summary:"):
            report["stages"][name]["prompt_fingerprint"] = analysis.prompt_fingerprint("summary")
            report["stages"][name]["body_fingerprint"] = fingerprint({"sections": [(s.locator, s.text) for s in body.sections], "source_url": body.source_url})
        save()  # Persist paid intention before the request.
        print(f"{name}: calling DeepSeek", flush=True)
        usage_cursor, observation_cursor, output_cursor = len(analysis.usage_records), len(client.observations), len(client.visible_outputs)
        try:
            result = operation()
            report["stages"][name].update(status="validated", result=result.to_dict())
            ok = True
        except Exception as exc:
            # Only controlled error codes are public, never HTTP objects.
            code = str(exc) if isinstance(exc, ProcessingError) and re.fullmatch(r"[a-z0-9_]+", str(exc)) else type(exc).__name__
            report["stages"][name].update(status="failed", error=code)
            if name.startswith("summary:") and len(client.visible_outputs) > output_cursor:
                # Local diagnosis retains only visible JSON, never the
                # provider envelope or hidden reasoning. tmp is Git-ignored.
                diagnostic = APP / "tmp" / "live-api" / "last-visible-summary.json"
                diagnostic.write_text(json.dumps(scrubber.clean(client.visible_outputs[-1]), ensure_ascii=False, indent=2), encoding="utf-8")
            ok = False
        report["usage"].extend(analysis.usage_records[usage_cursor:])
        report["observations"].extend(client.observations[observation_cursor:])
        save()
        print(f"{name}: {report['stages'][name]['status']}", flush=True)
        return ok

    analysis.on_usage = lambda: None
    ok = True
    try:
        if args.stage in {"all", "selection"}:
            for base_id in ("2308.00692", "2504.11008"):
                paper = papers[base_id]
                if not stage("selection:" + base_id, lambda p=paper: analysis.select(p, match_rules(p, config))):
                    ok = False
                    break  # Auth/transport failures must not prompt more calls.
        if args.stage in {"all", "summary"} and ok:
            selection = report["stages"].get("selection:2504.11008", {})
            decision = Decision.from_dict(selection["result"]) if selection.get("status") == "validated" else None
            if decision is None or decision.status != "select" or decision.tier != "full":
                print("summary: selection prerequisite missing; no paid request", flush=True)
                ok = False
            else:
                ok = stage("summary:2504.11008", lambda: analysis.summarize(papers["2504.11008"], body))
        summary_stage = report["stages"].get("summary:2504.11008", {})
        if summary_stage.get("status") == "validated":
            review = summary_stage.get("manual_review_result", {})
            current_body_hash = fingerprint({"sections": [(s.locator, s.text) for s in body.sections], "source_url": body.source_url})
            reviewed = review.get("summary") if review.get("body_fingerprint") == current_body_hash else None
            summary = Summary.from_dict(reviewed or summary_stage["result"])
            validate_summary(summary, body)
            items = [DigestItem(papers["2504.11008"], "full", summary)]
            lisa = report["stages"].get("selection:2308.00692", {})
            if lisa.get("status") == "validated" and lisa["result"]["status"] == "select" and lisa["result"]["tier"] == "light":
                items.append(DigestItem(papers["2308.00692"], "light"))
            day = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Shanghai")).date()
            (path.parent / "sample-digest.md").write_text(scrubber.text(render_archive(day, items, ["真实模型小规模联调，未发送微信，未改变生产状态。"])), encoding="utf-8")
    finally:
        client.close()
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProcessingError as exc:
        print(str(exc) if re.fullmatch(r"[a-z0-9_]+", str(exc)) else "smoke_check_failed")
        raise SystemExit(2)
