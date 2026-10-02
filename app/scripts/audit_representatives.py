"""Regenerate the fixed representative source audit without provider calls.

Run with the application's pinned Python dependencies on PYTHONPATH. This
script never downloads a paper or changes the manually authored fixture.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
import uuid

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from arxivdaily.fulltext import FulltextReader
from arxivdaily.llm import validate_summary
from arxivdaily.models import Paper, Summary
from arxivdaily.models import parse_time
from arxivdaily.config import load_config
from arxivdaily.pipeline import Pipeline
from arxivdaily.simulation import FixtureAnalysis, FixtureReader
from arxivdaily.state import StateStore

root = APP
source_dir = root / "fixtures" / "sources"
manifest = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8"))
fixture = json.loads((root / "fixtures" / "representative.json").read_text(encoding="utf-8"))
if hashlib.sha256((source_dir / "manifest.json").read_bytes()).hexdigest() != fixture["source_manifest_sha256"]:
    raise ValueError("source manifest changed after manual representative fixture authoring")
reader = FulltextReader(load_config(), root / "tmp" / "source-audit")
rows = []
for row in manifest["papers"]:
    paper = Paper.from_dict(row["metadata"])
    item = {"version_id": paper.version_id, "expected_route": fixture["decisions"][paper.base_id]["route"], "expected_tier": fixture["decisions"][paper.base_id]["tier"], "sources": []}
    html_body = None
    for source in row["sources"]:
        path = source_dir / source["path"]
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual_sha == source["sha256"]
        body = reader.parse_html(path.read_text(encoding="utf-8"), paper) if source["kind"] == "html" else reader.parse_pdf(path, paper)
        if source["kind"] == "pdf" and body.qualified:
            reader._prepare_visuals(path, paper, body)
        if source["kind"] == "html":
            if any(f.required for f in body.figures):
                visual_source = next(s for s in row["sources"] if s["kind"] == "pdf")
                visual_path = source_dir/visual_source["path"]
                if hashlib.sha256(visual_path.read_bytes()).hexdigest() != visual_source["sha256"]:
                    raise ValueError("visual source changed")
                reader.attach_html_visuals(visual_path,paper,body)
            html_body = body
        source_audit = {"kind": source["kind"], "path": f"fixtures/sources/{source['path']}", "sha256": actual_sha, "bytes": path.stat().st_size, "qualified": body.qualified, "read_chars": body.quality["read_chars"], "section_count": body.quality["section_count"], "gate_reasons": body.quality["reasons"]}
        source_audit["missing_parts"] = body.quality.get("missing_parts",[])
        source_audit["figure_page_map"] = body.quality.get("figure_page_map",{})
        source_audit["rendered_physical_pages"] = body.quality.get("rendered_physical_pages",[])
        if source["kind"] == "pdf":
            source_audit["physical_page_count"] = body.quality["physical_page_count"]
            source_audit["reading_order_strategies"] = dict(Counter(body.quality["reading_order_strategy"]))
            source_audit["rendered_physical_pages"] = body.quality.get("rendered_physical_pages", [])
            source_audit["rotated_text_pages"] = body.quality.get("rotated_text_pages",[])
        item["sources"].append(source_audit)
    assert html_body and html_body.qualified
    if paper.base_id in fixture["summaries"]:
        summary = Summary.from_dict(fixture["summaries"][paper.base_id])
        validate_summary(summary, html_body)
        item["manual_summary_evidence_validated"] = True
        item["summary_evidence_count"] = len(summary.evidence)
    else:
        item["manual_summary_evidence_validated"] = None
        item["summary_evidence_count"] = 0
    rows.append(item)

fixture_path = root / "fixtures" / "representative.json"
offline_analysis = FixtureAnalysis(fixture)
offline_reader = FixtureReader(load_config(),fixture,fixture_path,root / "tmp" / "source-audit")
offline_store = StateStore(root / "tmp" / "audit-runs" / uuid.uuid4().hex)
replay = Pipeline(load_config(),offline_store,None,offline_analysis,offline_reader,None,now=parse_time("2026-10-02T07:17:00+00:00")).run([Paper.from_dict(p) for p in fixture["papers"]])
report = {
    "audit_kind": "offline_real_source_parser_and_manual_fixture_audit",
    "model_called": False,
    "network_called": False,
    "manifest_sha256": hashlib.sha256((source_dir / "manifest.json").read_bytes()).hexdigest(),
    "fixture_path": "fixtures/representative.json",
    "offline_pipeline_replay": {"full": replay["full"], "light": replay["light"], "selection_calls": offline_analysis.calls["selection"], "summary_calls": offline_analysis.calls["summary"], "review_calls": offline_analysis.calls["review"], "errors": replay["errors"], "delivery_call": False},
    "papers": rows,
    "visual_review": [
        {"version_id": "2504.11008v2", "physical_pdf_page": 4, "observation": "Wide framework figure above two text columns; architecture caption and supervised baseline text are readable. The mixed layout requires separate full-width and column reading regions."},
        {"version_id": "2505.11872v4", "physical_pdf_page": 5, "observation": "Framework figure shows vision backbone, multimodal model and mask decoder; nearby text describes segmentation and text-generation losses. No RL training is shown."},
        {"version_id": "2603.19169v1", "physical_pdf_page": 6, "observation": "Reasoning figure visibly includes candidate generation, an RL agent, reject/confirm decisions and final stenosis output. This supports the separation of DPO perception from RL diagnostic reasoning."},
    ],
    "limitations": [
        "All four HTML and PDF versions pass the structured fulltext gate on these fixed sources. This does not guarantee correct extraction for arbitrary PDF layouts; sparse, scrambled, or unreadable pages still fail the gate.",
        "Manual fixture decisions and Chinese summaries are offline test expectations, not DeepSeek outputs or an end-to-end service validation.",
        "ARIADNE metadata abstract reports 0.838, while audited body results use other figures; the manual summary omits the uncorroborated abstract value.",
        "Visual page review and rendered key pages did not validate every image-only numeric value; manual summary numbers are grounded in extractable HTML sections or tables.",
    ],
}
target = root / "reports" / "representative-source-audit.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("wrote", target)
