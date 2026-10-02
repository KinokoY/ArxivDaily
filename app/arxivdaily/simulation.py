"""Scripted fixtures for offline verification, explicitly not model validation."""
from __future__ import annotations

import json
from pathlib import Path

from .fulltext import FulltextReader
from .models import Body, Decision, Paper, ProcessingError, Summary


class FixtureAnalysis:
    def __init__(self, fixture: dict):
        self.fixture = fixture
        self.usage_records = []
        self.calls = {"selection": 0, "review": 0, "summary": 0}

    def select(self, paper: Paper, hits: list[str]) -> Decision:
        self.calls["selection"] += 1
        try:
            return Decision.from_dict(self.fixture["decisions"][paper.base_id])
        except KeyError:
            raise ProcessingError("offline_selection_fixture_missing") from None

    def review(self, paper, body, decision):
        self.calls["review"] += 1
        data = self.fixture.get("reviews", {}).get(paper.base_id)
        return Decision.from_dict(data) if data else decision

    def summarize(self, paper, body):
        self.calls["summary"] += 1
        try:
            return Summary.from_dict(self.fixture["summaries"][paper.base_id])
        except KeyError:
            raise ProcessingError("offline_summary_fixture_missing") from None


class FixtureReader:
    def __init__(self, config: dict, fixture: dict, fixture_path: Path, work_dir: Path):
        self.fixture, self.fixture_path = fixture, fixture_path
        self.reader = FulltextReader(config, work_dir)
        self.calls = 0

    def read(self, paper):
        self.calls += 1
        if paper.base_id in self.fixture.get("bodies", {}):
            return Body.from_dict(self.fixture["bodies"][paper.base_id])
        source = self.fixture.get("sources", {}).get(paper.base_id)
        if not source:
            raise ProcessingError("offline_fulltext_fixture_missing")
        path = (self.fixture_path.parent / source["path"]).resolve()
        if not path.is_relative_to(self.fixture_path.parent.resolve()):
            raise ProcessingError("fixture_source_outside_fixture_directory")
        import hashlib
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ProcessingError("fixture_source_hash_mismatch")
        body = self.reader.parse_html(data.decode("utf-8"), paper) if source["kind"] == "html" else self.reader.parse_pdf(path, paper)
        if source["kind"] == "html" and any(f.required for f in body.figures):
            manifest = json.loads((path.parent/"manifest.json").read_text(encoding="utf-8"))
            entry = next(row for row in manifest["papers"] if row["version_id"] == paper.version_id)
            pdf = next(s for s in entry["sources"] if s["kind"] == "pdf")
            pdf_path = (path.parent/pdf["path"]).resolve()
            if not pdf_path.is_relative_to(path.parent) or hashlib.sha256(pdf_path.read_bytes()).hexdigest() != pdf["sha256"]:
                raise ProcessingError("fixture_visual_source_hash_mismatch")
            self.reader.attach_html_visuals(pdf_path,paper,body)
        if source["kind"] == "pdf" and body.qualified:
            self.reader._prepare_visuals(path, paper, body)
        return body


def load_fixture(path: str | Path) -> tuple[dict, list[Paper]]:
    path = Path(path)
    result = json.loads(path.read_text(encoding="utf-8"))
    return result, [Paper.from_dict(p) for p in result["papers"]]
