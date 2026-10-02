from pathlib import Path

from arxivdaily.fulltext import FulltextReader
from arxivdaily.models import Paper, ProcessingError


def paper():
    return Paper("2504.11008v2", "Example medical segmentation", "The abstract describes a mask task.", ["cs.CV"], "2025-04-15T00:00:00+00:00", "2025-05-01T00:00:00+00:00")


def test_html_keeps_appendix_and_captions(tmp_path):
    reader = FulltextReader({"fulltext": {"min_chars": 100}}, tmp_path)
    html = """<html><body><article>
      <section><h2>1 Introduction</h2><p>A practical segmentation problem has limited supervision and a difficult target definition.</p></section>
      <section><h2>2 Method</h2><p>We train a mask predictor using a topology-aware preference objective with matched masks.</p></section>
      <section><h2>3 Experiments</h2><p>We evaluate on a held-out imaging benchmark and compare the same baseline.</p>
      <table><caption>Table 1: Held-out benchmark scores</caption><tr><td>12</td></tr></table></section>
      <section><h2>Appendix A Additional Evaluation</h2><p>The late appendix describes the failure analysis and additional patient subsets.</p></section>
      <section><h2>References</h2><p>Reference matter must be excluded from evidence.</p></section>
    </article></body></html>"""
    body = reader.parse_html(html, paper())
    assert body.qualified
    assert body.source_url.endswith("2504.11008v2")
    assert any("Appendix" in section.locator for section in body.sections)
    assert all("References" not in section.locator for section in body.sections)
    assert body.figures[0].label == "Table 1"
    assert body.figures[0].locator == "caption:Table 1"


def test_html_missing_method_fails_even_if_long(tmp_path):
    reader = FulltextReader({"fulltext": {"min_chars": 100}}, tmp_path)
    html = "<article><section><h2>Introduction</h2><p>" + "Context sentence. " * 100 + "</p></section><section><h2>Experiments</h2><p>" + "Result sentence. " * 100 + "</p></section></article>"
    body = reader.parse_html(html, paper())
    assert not body.qualified
    assert "method_section_missing" in body.quality["reasons"]


def test_pdf_missing_text_fails_without_abstract_fallback(tmp_path):
    from pypdf import PdfWriter
    path = tmp_path / "empty.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as stream:
        writer.write(stream)
    reader = FulltextReader({"fulltext": {"min_chars": 100}}, tmp_path)
    body = reader.parse_pdf(path, paper())
    assert not body.qualified
    assert body.quality["missing_pages"] == [1]
    assert body.sections[0].locator == "pdf-page:1"


def test_pdf_physical_pages_and_render(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    for heading, sentence in [
        ("Methods", "We train the mask predictor with topology-aware paired preferences and a coherent optimization objective."),
        ("Experiments", "We compare held-out medical images and report Dice 0.85 against a baseline with Dice 0.80."),
    ]:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        commands = f"BT /F1 12 Tf 50 700 Td ({heading}) Tj 0 -22 Td ({sentence}) Tj 0 -22 Td ({sentence}) Tj ET".encode("ascii")
        stream = DecodedStreamObject()
        stream.set_data(commands)
        page[NameObject("/Contents")] = writer._add_object(stream)
    path = tmp_path / "structured.pdf"
    with path.open("wb") as stream:
        writer.write(stream)
    reader = FulltextReader({"fulltext": {"min_chars": 100}}, tmp_path)
    body = reader.parse_pdf(path, paper())
    assert body.qualified, body.quality
    assert [section.locator for section in body.sections] == ["pdf-page:1", "pdf-page:2"]
    assert body.quality["has_method"] and body.quality["has_evaluation_or_theory"]
    image = reader.render_page(path, 2, tmp_path / "physical-page-2.png")
    assert image.is_file() and image.stat().st_size > 1000


def test_nested_html_keeps_parent_method_intro(tmp_path):
    reader = FulltextReader({"fulltext": {"min_chars": 100}}, tmp_path)
    html = """<article>
    <section><h2>Methods</h2><p>The parent introduces the optimization objective and topology constraint in detail.</p>
      <section><h3>Training</h3><p>Paired masks train the preference loss with stable gradients and multiple medical images.</p></section>
    </section>
    <section><h2>Evaluation</h2><p>Held-out images provide a fair comparison with the prior segmentation baseline.</p>
      <table><caption>Table 2: Dice scores</caption><tr><td>Baseline</td><td>0.80</td></tr><tr><td>New</td><td>0.85</td></tr></table>
    </section></article>"""
    body = reader.parse_html(html, paper())
    assert body.qualified, body.quality
    assert any("parent introduces" in section.text for section in body.sections)
    assert any("Methods / Training" in section.locator for section in body.sections)
    assert any(section.kind == "table" and "0.85" in section.text for section in body.sections)


def test_latexml_equation_tables_stay_in_method_and_unnumbered_tables_keep_html_identity(tmp_path):
    reader = FulltextReader({"fulltext": {"min_chars": 100}}, tmp_path)
    html = """<article>
      <section><h2>Methods</h2><p>We optimize the segmentation objective with supervision.</p>
        <table class="ltx_equationgroup ltx_eqn_table" id="S1.E1"><tr><td>L = Dice + BCE</td></tr></table>
        <p>The equation controls training of the proposed mask predictor.</p></section>
      <section><h2>Experiments</h2><p>We compare against a matched baseline on held-out images.</p>
        <table id="S2.TX"><tr><td>Baseline Dice 0.80</td></tr></table>
        <table><tr><td>New model Dice 0.85</td></tr></table></section>
    </article>"""
    body = reader.parse_html(html, paper())
    assert body.qualified, body.quality
    method = next(section for section in body.sections if section.locator == "section:Methods")
    assert "L = Dice + BCE" in method.text
    assert "equation controls training" in method.text
    assert [section.locator for section in body.sections if section.kind == "table"] == [
        "table:html-id:S2.TX", "table:html-node:2"
    ]
    assert not any("Table 1" in section.locator for section in body.sections)


def test_real_medisee_html_uses_figure_captions_for_tables_and_retains_formulas(tmp_path):
    import hashlib
    import json

    root = Path(__file__).resolve().parents[1] / "fixtures" / "sources"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    entry = next(row for row in manifest["papers"] if row["version_id"] == "2504.11008v2")
    source = next(item for item in entry["sources"] if item["kind"] == "html")
    html_path = root / source["path"]
    assert hashlib.sha256(html_path.read_bytes()).hexdigest() == source["sha256"]
    body = FulltextReader({"fulltext": {"min_chars": 2500}}, tmp_path).parse_html(
        html_path.read_text(encoding="utf-8"), Paper.from_dict(entry["metadata"])
    )
    assert body.qualified, body.quality
    tables = {section.locator: section.text for section in body.sections if section.kind == "table"}
    assert list(tables) == [f"table:Table {number}" for number in range(1, 7)]
    assert "medical reasoning segmentation" in tables["table:Table 1"].lower()
    assert "medical reasoning detection" in tables["table:Table 2"].lower()
    assert {figure.locator for figure in body.figures if figure.label in {"Table 1", "Table 2"}} == {
        "caption:Table 1", "caption:Table 2"
    }
    method = next(section for section in body.sections if "Overall Optimization" in section.locator)
    assert "Equations:" in method.text
    assert "mathcal{L}_{sim}" in method.text
    assert "table:Table 7" not in body.quality["read_locators"]


def test_two_column_pdf_uses_column_order(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")}))
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    commands = []
    for row in range(14):
        y = 650 - row * 28
        left = "Methods" if row == 0 else "Left method evidence repeated with detailed support"
        right = "Experiments" if row == 0 else "Right experiment evidence here with detailed result"
        commands.append(f"BT /F1 10 Tf 50 {y} Td ({left}) Tj ET")
        commands.append(f"BT /F1 10 Tf 330 {y} Td ({right}) Tj ET")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    path = tmp_path / "columns.pdf"
    with path.open("wb") as output:
        writer.write(output)
    reader = FulltextReader({"fulltext": {"min_chars": 100}}, tmp_path)
    body = reader.parse_pdf(path, paper())
    assert body.quality["reading_order_strategy"] == ["two_column_pdfium"]
    assert body.qualified, body.quality
    assert body.sections[0].text.index("Left method") < body.sections[0].text.index("Right experiment")


def test_hashed_representative_html_sources_support_manual_summaries(tmp_path):
    from arxivdaily.llm import validate_summary
    from arxivdaily.models import Summary
    from arxivdaily.simulation import FixtureReader, load_fixture

    path = Path(__file__).resolve().parents[1] / "fixtures" / "representative.json"
    fixture, papers = load_fixture(path)
    reader = FixtureReader({"fulltext": {"min_chars": 2500}}, fixture, path, tmp_path)
    assert fixture["fixture_kind"] == "representative_manual_offline_mock_not_model_validation"
    for paper in papers:
        body = reader.read(paper)
        assert body.qualified, (paper.version_id, body.quality)
        if paper.base_id in fixture["summaries"]:
            validate_summary(Summary.from_dict(fixture["summaries"][paper.base_id]), body)
    assert fixture["decisions"]["2308.00692"]["tier"] == "light"
    assert fixture["decisions"]["2603.19169"]["dpo_is_method"]
    assert fixture["decisions"]["2603.19169"]["rl_is_method"]


def test_sparse_interleaved_columns_stay_unqualified(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")}))
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    commands = []
    for row in range(3):
        y = 650 - row * 24
        commands.extend([
            f"BT /F1 10 Tf 50 {y} Td (Left method paragraph with enough detail to be credible.) Tj ET",
            f"BT /F1 10 Tf 330 {y} Td (Right experiment results with enough detail to be credible.) Tj ET",
        ])
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    path = tmp_path / "sparse-interleaved.pdf"
    with path.open("wb") as output:
        writer.write(output)
    body = FulltextReader({"fulltext": {"min_chars": 100}}, tmp_path).parse_pdf(path, paper())
    assert not body.qualified
    assert "reading_order_uncertain" in body.quality["reasons"]


def test_representative_pdf_pages_have_structured_reading_order(tmp_path):
    import json
    import hashlib

    source_dir = Path(__file__).resolve().parents[1] / "fixtures" / "sources"
    manifest = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8"))
    reader = FulltextReader({"fulltext": {"min_chars": 2500}}, tmp_path)
    for row in manifest["papers"]:
        paper = Paper.from_dict(row["metadata"])
        source = next(item for item in row["sources"] if item["kind"] == "pdf")
        path = source_dir / source["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
        body = reader.parse_pdf(path, paper)
        assert body.qualified, (paper.version_id, body.quality["reasons"])
        assert body.quality["has_method"] and body.quality["has_evaluation_or_theory"]
        assert len(body.sections) == body.quality["physical_page_count"]
        assert all(section.locator.startswith("pdf-page:") for section in body.sections)
        assert "ambiguous_columns" not in body.quality["reading_order_strategy"]


def test_real_pdf_fallback_download_parse_render_and_local_cleanup(tmp_path):
    import httpx
    import json
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root/"fixtures/sources/manifest.json").read_text(encoding="utf-8"))
    metadata = next(row["metadata"] for row in manifest["papers"] if row["version_id"] == "2504.11008v2")
    p = Paper.from_dict(metadata)
    pdf = (root/"fixtures/sources/2504.11008v2.pdf").read_bytes()
    def serve(request):
        return httpx.Response(404) if "/html/" in str(request.url) else httpx.Response(200,content=pdf)
    reader = FulltextReader({"fulltext":{"min_chars":2500}},tmp_path,httpx.Client(transport=httpx.MockTransport(serve)))
    result = reader.read(p)
    assert result.qualified and result.source_type == "pdf"
    assert result.quality["html_fallback_reason"] == "source_unavailable"
    assert result.quality["rendered_physical_pages"]
    assert not (tmp_path/"2504.11008v2.pdf").exists()
    assert all(Path(f.image_path).is_file() for f in result.figures if f.required)


def test_qualified_html_supplies_needed_same_version_figure_images_to_summary(tmp_path,monkeypatch):
    import json
    import httpx
    from arxivdaily.config import load_config
    from arxivdaily.llm import AnalysisClient
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root/"fixtures/representative.json").read_text(encoding="utf-8"))
    p = Paper.from_dict(next(p for p in fixture["papers"] if p["version_id"] == "2504.11008v2"))
    sources = root/"fixtures/sources"
    def serve(request):
        content = (sources/(p.version_id+(".html" if "/html/" in str(request.url) else ".pdf"))).read_bytes()
        return httpx.Response(200,content=content)
    reader = FulltextReader(load_config(),tmp_path,httpx.Client(transport=httpx.MockTransport(serve)))
    document = reader.read(p)
    assert document.source_type == "html" and document.qualified
    assert document.quality["figure_page_map"] and document.quality["visual_evidence_prepared"]
    assert not document.quality["visual_evidence_used"]
    monkeypatch.setenv("DEEPSEEK_API_KEY","fake-model-runtime-key")
    calls = []
    def model(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200,json={"model":"deepseek-flash","usage":{"prompt_tokens":100,"completion_tokens":50},"choices":[{"finish_reason":"stop","message":{"content":json.dumps(fixture["summaries"][p.base_id],ensure_ascii=False)}}]})
    summary = AnalysisClient(load_config(),httpx.Client(transport=httpx.MockTransport(model))).summarize(p,document)
    content = calls[0]["messages"][1]["content"]
    assert any(part["type"] == "image_url" for part in content)
    assert document.quality["visual_evidence_used"] and summary.method
    assert not list(tmp_path.glob("*.pdf"))
