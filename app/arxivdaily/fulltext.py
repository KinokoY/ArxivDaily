"""Versioned arXiv full text extraction with a conservative quality gate.

Raw documents and rendered pages stay in the local work directory.  Only the
Body.quality metadata is suitable for a public checkpoint.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import math
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import httpx
from pypdf import PdfReader

from .models import Body, Figure, Paper, ProcessingError, Section


_METHOD = re.compile(r"\b(methods?|methodology|approach|framework|algorithm|model|objective|optimization|theor(?:y|em)s?|proof)\b", re.I)
_EVALUATION = re.compile(r"\b(experiments?|evaluation|results?|benchmark|ablation|analysis|discussion|proof|theor(?:y|em)s?)\b", re.I)
_BODY_END = re.compile(r"\b(references|bibliography|acknowledg(?:e)?ments?)\b", re.I)
_CAPTION = re.compile(r"^\s*((?i:figure|fig\.?|table)\s*[A-Z]?\d+(?:[A-Za-z](?![A-Za-z]))?)(?:\s*[:.\-]\s*\S.*|\s+(?=[A-Z])\S.*|(?=[A-Z][a-z])\S.*)$")
_KEY_VISUAL = re.compile(r"\b(table|result|performance|comparison|ablation|architecture|framework|topology|quantitative|qualitative|visualization|pipeline)\b", re.I)
_PDF_SHORT_HEADING = re.compile(r"^(?:(?:materials?\s+(?:and|&)\s+)?methods?|methodology|approach|framework|experiments?|experimental\s+(?:results?|evaluation|setup)|evaluation|results?|theory|theoretical\s+analysis|proof|appendix)$", re.I)
_PDF_NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)*\.?\s+[A-Z][A-Za-z0-9\s,:/()\-]{2,74}$")


def _pdf_heading(line: str) -> str | None:
    value = _clean(line)
    if not value or value.endswith((".", ";", ",")):
        return None
    return value if _PDF_SHORT_HEADING.fullmatch(value) or _PDF_NUMBERED_HEADING.fullmatch(value) else None


def _pdfium_ordered_text(pdfium_page, fallback: str) -> tuple[str, str, bool]:
    """Read prose columns after a full-width title/figure band when geometry supports it."""
    textpage = pdfium_page.get_textpage()
    width, height = pdfium_page.get_size()
    boxes: list[tuple[float, float, float]] = []
    for i in range(textpage.count_chars()):
        try:
            left, bottom, right, top = textpage.get_charbox(i)
        except Exception:
            continue
        if right - left < 0.5 or top - bottom < 1:
            continue
        boxes.append(((bottom + top) / 2, left, right))
    boxes.sort(key=lambda item: -item[0])
    rows: list[list] = []
    for y, left, right in boxes:
        if not rows or abs(y - rows[-1][0]) > 4:
            rows.append([y, [(left, right)]])
        else:
            rows[-1][1].append((left, right))
    prose_rows: list[tuple[float, float]] = []
    short_dual_rows: list[float] = []
    single_prose_rows = 0
    for y, intervals in rows:
        if len(intervals) < 10 or not 0.07 * height <= y <= 0.92 * height:
            continue
        intervals.sort()
        if not (intervals[0][0] < 0.45 * width and intervals[-1][1] > 0.55 * width):
            continue
        if len(intervals) < 70:
            wide_gaps = [(left - prev_right, (left + prev_right) / 2) for (_, prev_right), (left, _) in zip(intervals, intervals[1:]) if 0.25 * width < (left + prev_right) / 2 < 0.65 * width]
            if wide_gaps:
                gap, _ = max(wide_gaps)
                if 15 <= gap <= 0.5 * width:
                    short_dual_rows.append(y)
            continue
        gaps = [(left - prev_right, (left + prev_right) / 2) for (_, prev_right), (left, _) in zip(intervals, intervals[1:]) if 0.40 * width < (left + prev_right) / 2 < 0.60 * width]
        if not gaps:
            continue
        gap, middle = max(gaps)
        if 15 <= gap <= 0.35 * width and abs(middle - width / 2) < 0.15 * width:
            prose_rows.append((y, middle))
        elif gap <= 10:
            single_prose_rows += 1
    two_columns = len(prose_rows) >= 5 and len(prose_rows) / max(1, len(rows)) >= 0.05
    if two_columns:
        split = sorted(middle for _, middle in prose_rows)[len(prose_rows) // 2]
        first_prose = max(y for y, _ in prose_rows)
        nearby_short = [y for y in short_dual_rows if first_prose < y <= first_prose + 36]
        top_cut = min(height, max([first_prose, *nearby_short]) + 8)
        top = textpage.get_text_bounded(left=0, bottom=top_cut, right=width, top=height)
        left = textpage.get_text_bounded(left=0, bottom=0, right=split, top=top_cut)
        right = textpage.get_text_bounded(left=split, bottom=0, right=width, top=top_cut)
        reconstructed = "\n".join(part for part in (top, left, right) if part.strip())
        full = textpage.get_text_bounded(left=0, bottom=0, right=width, top=height)
        coverage = len(_clean(reconstructed)) / max(1, len(_clean(full)))
        return reconstructed, "two_column_pdfium", 0.82 <= coverage <= 1.18
    lines = [line for line in fallback.splitlines() if line.strip()]
    interleaved = sum(bool(re.search(r"\S\s{12,}\S", line)) for line in lines)
    confident = not lines or single_prose_rows >= 8 or interleaved / len(lines) < 0.15
    return fallback, "single_column_layout" if confident else "ambiguous_columns", confident


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _own_heading(section_node) -> str:
    for heading in section_node.find_all(re.compile("^h[1-6]$")):
        if heading.find_parent("section") is section_node:
            return _clean(heading.get_text(" ", strip=True))
    return _clean(section_node.get("id", ""))


def _is_data_table(node) -> bool:
    """LaTeXML renders displayed equations as tables; they are prose evidence."""
    if node.name != "table":
        return False
    classes = set(node.get("class", []))
    return not any(value.startswith(("ltx_eqn", "ltx_equation")) for value in classes)


def _table_caption(node):
    caption = node.find("caption", recursive=False) or node.select_one(".ltx_caption")
    if caption is not None:
        return caption
    figure = node.find_parent("figure")
    if figure is not None and "ltx_table" in figure.get("class", []):
        return figure.find("figcaption") or figure.select_one(".ltx_caption")
    return None


def _table_identity(node, ordinal: int) -> tuple[str, str, str]:
    caption = _table_caption(node)
    caption_text = _clean(caption.get_text(" ", strip=True)) if caption else ""
    match = _CAPTION.match(caption_text)
    if match and match.group(1).casefold().startswith("table"):
        label = match.group(1)
        return f"table:{label}", label, caption_text
    figure = node.find_parent("figure")
    marker = node.get("id") or (figure.get("id") if figure is not None else "")
    if isinstance(marker, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]*", marker):
        return f"table:html-id:{marker}", f"HTML table id {marker}", caption_text
    return f"table:html-node:{ordinal}", f"HTML table node {ordinal}", caption_text


def _quality(body: Body, min_chars: int, *, order_ok: bool, missing_pages: list[int] | None = None) -> None:
    """Compute an auditable gate from body structure, coverage and extraction quality."""
    missing_pages = missing_pages or []
    sections = [s for s in body.sections if s.text.strip()]
    headings = " ".join(s.locator for s in sections)
    text = " ".join(s.text for s in sections)
    method = bool(_METHOD.search(headings))
    if not method and body.source_type == "html":
        # Some papers title their methods section after the proposed system
        # (e.g. "4 PRS-Med") and put "Overall Architecture" in its prose.
        method = any(
            section.kind == "section"
            and not re.search(r"introduction|related work|experiment|evaluation|result|discussion|conclusion", section.locator, re.I)
            and re.search(r"\b(overall architecture|model architecture|proposed framework|proposed model|our method|our approach)\b", section.text[:300], re.I)
            for section in sections
        )
    evaluation = bool(_EVALUATION.search(headings))
    # A relevant caption may locate evidence but cannot replace the text of a
    # missing method/evaluation section.
    reasons: list[str] = []
    if len(text) < min_chars:
        reasons.append("too_short")
    if len(sections) < 2:
        reasons.append("no_section_structure")
    if not method:
        reasons.append("method_section_missing")
    if not evaluation:
        reasons.append("evaluation_or_theory_section_missing")
    if not order_ok:
        reasons.append("reading_order_uncertain")
    if missing_pages:
        reasons.append("missing_or_unreadable_pages")
    if len(text) and text.count("\ufffd") / len(text) > 0.001:
        reasons.append("replacement_glyphs")
    body.quality = {
        "passed": not reasons,
        "reasons": reasons,
        "source_type": body.source_type,
        "version_id": body.version_id,
        "source_url": body.source_url,
        "section_count": len(sections),
        "read_chars": len(text),
        "read_locators": [s.locator for s in sections],
        "has_method": method,
        "has_evaluation_or_theory": evaluation,
        "reading_order_ok": order_ok,
        "missing_pages": missing_pages,
        "figures_or_tables": [f.label for f in body.figures],
        "visual_evidence_used": False,
    }


class FulltextReader:
    def __init__(self, config: dict, work_dir: str | Path, client: httpx.Client | None = None):
        self.config = config.get("fulltext", config)
        self.work_dir = Path(work_dir).resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.client = client or httpx.Client(timeout=float(self.config.get("timeout", 30)), follow_redirects=True)

    def _get(self, url: str) -> bytes:
        # Every URL is constructed from a validated arXiv ID.  Redirects may
        # move between arxiv.org hosts, but never to an arbitrary host.
        max_bytes = int(self.config.get("max_download_bytes", 30_000_000))
        attempts = max(1, int(self.config.get("attempts", 3)))
        for attempt in range(attempts):
            try:
                if hasattr(self.client, "stream"):
                    with self.client.stream("GET", url) as response:
                        self._check_response(response)
                        chunks = []
                        size = 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > max_bytes:
                                raise ProcessingError("source_too_large")
                            chunks.append(chunk)
                        return b"".join(chunks)
                response = self.client.get(url)
                self._check_response(response)
                if len(response.content) > max_bytes:
                    raise ProcessingError("source_too_large")
                return response.content
            except ProcessingError:
                raise
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {429, 500, 502, 503, 504}:
                    raise ProcessingError("source_http_error") from None
                if attempt == attempts - 1:
                    raise ProcessingError("source_request_failed") from None
        raise ProcessingError("source_request_failed")

    @staticmethod
    def _check_response(response: httpx.Response) -> None:
        if response.status_code == 404:
            raise ProcessingError("source_unavailable")
        response.raise_for_status()
        host = (urlparse(str(response.url)).hostname or "").lower()
        if host not in {"arxiv.org", "export.arxiv.org", "www.arxiv.org"}:
            raise ProcessingError("unexpected_source_host")

    def read(self, paper: Paper) -> Body:
        html_error = "html_unavailable"
        try:
            data = self._get(f"https://arxiv.org/html/{paper.version_id}")
            body = self.parse_html(data.decode("utf-8", errors="replace"), paper)
            if body.qualified:
                if any(f.required for f in body.figures):
                    visual_pdf = self.work_dir / f"{paper.version_id.replace('/', '_')}-visual.pdf"
                    try:
                        pdf_data = self._get(f"https://arxiv.org/pdf/{paper.version_id}")
                        if not pdf_data.startswith(b"%PDF"):
                            raise ProcessingError("visual_pdf_response_invalid")
                        visual_pdf.write_bytes(pdf_data)
                        self.attach_html_visuals(visual_pdf,paper,body)
                    finally:
                        visual_pdf.unlink(missing_ok=True)
                return body
            html_error = ",".join(body.quality["reasons"])
        except ProcessingError as exc:
            html_error = str(exc)
        data = self._get(f"https://arxiv.org/pdf/{paper.version_id}")
        if not data.startswith(b"%PDF"):
            raise ProcessingError("pdf_response_invalid")
        path = self.work_dir / f"{paper.version_id.replace('/', '_')}.pdf"
        path.write_bytes(data)
        try:
            body = self.parse_pdf(path, paper)
            if body.qualified:
                self._prepare_visuals(path, paper, body)
        finally:
            path.unlink(missing_ok=True)
        body.quality["html_fallback_reason"] = html_error
        if not body.qualified:
            raise ProcessingError("fulltext_quality_failed:" + ",".join(body.quality["reasons"]))
        return body

    def parse_html(self, html: str, paper: Paper) -> Body:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one("article") or soup.select_one("main") or soup.body
        if root is None:
            raise ProcessingError("html_body_missing")
        for tag in root.select("script,style,nav,header,footer,aside,.ltx_bibliography,.ltx_acknowledgements"):
            tag.decompose()
        sections: list[Section] = []
        figures: list[Figure] = []
        seen: Counter[str] = Counter()
        table_info = {
            id(node): _table_identity(node, ordinal)
            for ordinal, node in enumerate(
                (table for table in root.find_all("table") if _is_data_table(table)), 1
            )
        }
        section_nodes = root.select("section")
        if section_nodes:
            # Each section contributes its own text; nested subsections are
            # removed from the copy and processed later in DOM order. Parent
            # headings remain in child locators even if the parent has no prose.
            for node in root.find_all(["section", "table"]):
                if node.name == "table" and id(node) not in table_info:
                    continue
                ancestor_sections = [a for a in node.parents if getattr(a, "name", None) == "section"]
                lineage = list(reversed(ancestor_sections)) + ([node] if node.name == "section" else [])
                names = [_own_heading(section_node) for section_node in lineage]
                if any(_BODY_END.fullmatch(name) for name in names if name):
                    continue
                if node.name == "table":
                    locator, _, caption_text = table_info[id(node)]
                    value = _clean(f"{caption_text} {node.get_text(' ', strip=True)}")
                    if len(value) >= 12:
                        sections.append(Section(locator, value, "table"))
                    continue
                name = " / ".join(part for part in names if part) or f"Unnamed {len(sections)+1}"
                seen[name] += 1
                locator = f"section:{name}" + (f"#{seen[name]}" if seen[name] > 1 else "")
                copy = BeautifulSoup(str(node), "html.parser")
                for descendant in copy.select("section section"):
                    descendant.decompose()
                equations: list[str] = []
                for descendant in copy.select("table"):
                    if not _is_data_table(descendant):
                        equation = _clean(descendant.get_text(" ", strip=True))
                        if equation:
                            equations.append(equation)
                    descendant.decompose()
                value = _clean(copy.get_text(" ", strip=True))
                if equations:
                    # Keep formula text in the method locator without breaking
                    # prose quotations that cross a displayed equation.
                    value += " Equations: " + " ; ".join(equations)
                if len(value) >= 40:
                    sections.append(Section(locator, value))
        else:
            # Flat scholarly HTML: collect consecutive heading-bounded blocks.
            current_name = "Introduction"
            fragments: list[str] = []
            def flush() -> None:
                value = _clean(" ".join(fragments))
                if len(value) >= 40 and not _BODY_END.fullmatch(current_name):
                    seen[current_name] += 1
                    locator = f"section:{current_name}" + (f"#{seen[current_name]}" if seen[current_name] > 1 else "")
                    sections.append(Section(locator, value))
            for child in root.find_all(re.compile("^h[1-6]$|^p$")):
                if child.name.startswith("h"):
                    flush()
                    current_name = _clean(child.get_text(" ", strip=True))
                    fragments = []
                elif not child.find_parent("figure"):
                    fragments.append(child.get_text(" ", strip=True))
            flush()
        for node in root.select("figure,table"):
            table = None
            if node.name == "table":
                if id(node) not in table_info or node.find_parent("figure") is not None:
                    continue
                table = node
            else:
                table = next((child for child in node.find_all("table") if id(child) in table_info), None)
            if table is not None:
                _, label, value = table_info[id(table)]
                if value:
                    locator = f"caption:{label}" if label.startswith("Table ") else f"caption:{table_info[id(table)][0].removeprefix('table:')}"
                    figures.append(Figure(label, locator, value))
                continue
            caption = node.find("figcaption") or node.find("caption") or node.select_one(".ltx_caption")
            if caption is None:
                continue
            value = _clean(caption.get_text(" ", strip=True))
            match = _CAPTION.match(value)
            label = match.group(1) if match else f"{node.name} {len(figures)+1}"
            # Extracted HTML tables already provide numeric evidence. Figures
            # describing methods or results need their same-version visual.
            required = not label.casefold().startswith("table") and node.name == "figure" and node.find("table") is None and bool(_KEY_VISUAL.search(value))
            figures.append(Figure(label, f"caption:{label}", value,required=required))
        body = Body(paper.version_id, f"https://arxiv.org/html/{paper.version_id}", "html", sections, figures)
        _quality(body, int(self.config.get("min_chars", 2500)), order_ok=True)
        body.quality["missing_parts"] = []
        return body

    def attach_html_visuals(self,pdf_path: Path,paper: Paper,body: Body) -> None:
        """Bind needed HTML figures to physical pages of the exact PDF version."""
        required = [f for f in body.figures if f.required]
        if not required:
            return
        pdf_body = self.parse_pdf(pdf_path,paper)
        def label_key(label):
            return re.sub(r"^(?:figure|fig\.?)","figure",re.sub(r"\s+","",label.casefold()))
        page_map = {}
        for figure in required:
            pages = {int(match.group(1)) for candidate in pdf_body.figures if label_key(candidate.label) == label_key(figure.label) and (match := re.match(r"pdf-page:(\d+):caption:",candidate.locator))}
            if len(pages) != 1:
                raise ProcessingError("html_figure_page_unlocated_or_ambiguous")
            page_map[figure.label] = next(iter(pages))
        if len(set(page_map.values())) > int(self.config.get("max_visual_pages",8)):
            raise ProcessingError("critical_visual_pages_exceed_limit")
        rendered = {}
        for page_number in sorted(set(page_map.values())):
            target = self.work_dir / f"{paper.version_id.replace('/', '_')}-page-{page_number}.png"
            self.render_page(pdf_path,page_number,target)
            rendered[page_number] = str(target)
        for figure in required:
            figure.image_path = rendered[page_map[figure.label]]
        body.quality["visual_source_url"] = f"https://arxiv.org/pdf/{paper.version_id}"
        body.quality["figure_page_map"] = page_map
        body.quality["rendered_physical_pages"] = sorted(rendered)
        body.quality["visual_evidence_prepared"] = True

    def parse_pdf(self, path: str | Path, paper: Paper) -> Body:
        pdfium_doc = None
        reader = None
        try:
            import pypdfium2 as pdfium
            reader = PdfReader(str(path), strict=False)
            if reader.is_encrypted:
                raise ProcessingError("pdf_encrypted")
            pdfium_doc = pdfium.PdfDocument(str(path))
            if len(pdfium_doc) != len(reader.pages):
                raise ProcessingError("pdf_page_count_mismatch")
            sections: list[Section] = []
            figures: list[Figure] = []
            missing: list[int] = []
            page_lines: list[str] = []
            strategies: list[str] = []
            order_flags: list[bool] = []
            rotated_pages: list[int] = []
            short_lines = 0
            lines_total = 0
            for index, page in enumerate(reader.pages, start=1):
                fallback = (page.extract_text(extraction_mode="layout") or "") if "/Contents" in page else ""
                pdf_page = pdfium_doc.get_page(index - 1)
                try:
                    angles = pdf_page.get_textpage()
                    try:
                        page_width,page_height = pdf_page.get_size()
                        rotated_content = False
                        for character in range(angles.count_chars()):
                            if abs(math.sin(pdfium.raw.FPDFText_GetCharAngle(angles.raw,character))) <= 0.05:
                                continue
                            left,bottom,right,top = angles.get_charbox(character)
                            x,y = (left+right)/2,(bottom+top)/2
                            if 0.08*page_width < x < 0.94*page_width and 0.06*page_height < y < 0.94*page_height:
                                rotated_content = True
                                break
                        if rotated_content:
                            rotated_pages.append(index)
                    finally:
                        angles.close()
                    raw, strategy, confident = _pdfium_ordered_text(pdf_page, fallback)
                finally:
                    pdf_page.close()
                strategies.append(strategy)
                order_flags.append(confident)
                page_lines.append(raw)
                lines = [x.strip() for x in raw.splitlines() if x.strip()]
                if len(_clean(raw)) < 80:
                    missing.append(index)
                lines_total += len(lines)
                short_lines += sum(len(x) <= 2 for x in lines)
                # Page locators are physical, one-based PDF file positions.
                sections.append(Section(f"pdf-page:{index}", _clean(raw)))
                seen_captions: set[str] = set()
                for line in [*raw.splitlines(), *fallback.splitlines()]:
                    match = _CAPTION.match(line)
                    if match:
                        label = _clean(match.group(1))
                        if label in seen_captions:
                            continue
                        seen_captions.add(label)
                        caption = _clean(line)
                        figures.append(Figure(label, f"pdf-page:{index}:caption:{label}", caption, required=bool(_KEY_VISUAL.search(caption))))
            # Repeated running headers/footers are removed before evidence is
            # offered to the model. Their repetition is recorded in metadata.
            edge_counts: Counter[str] = Counter()
            for raw in page_lines:
                lines = [line for line in raw.splitlines() if line.strip()]
                edge_counts.update({_clean(line) for line in lines[:2] + lines[-2:]})
            repeated_edges = {line for line, count in edge_counts.items() if len(reader.pages) >= 2 and count >= 2 and count / len(reader.pages) >= 0.5 and 4 <= len(line) <= 100 and not _pdf_heading(line)}
            if repeated_edges:
                for position, raw in enumerate(page_lines):
                    kept = [line for line in raw.splitlines() if _clean(line) not in repeated_edges]
                    page_lines[position] = "\n".join(kept)
                    sections[position].text = _clean(page_lines[position])
                lines_total = sum(len([line for line in raw.splitlines() if line.strip()]) for raw in page_lines)
                short_lines = sum(len(line.strip()) <= 2 for raw in page_lines for line in raw.splitlines() if line.strip())
                missing = [position for position, raw in enumerate(page_lines, start=1) if len(_clean(raw)) < 80]
            # A large fraction of one/two-character lines is typical of broken
            # extraction or interleaved glyphs.  Such a document cannot pass.
            order_ok = lines_total > 0 and short_lines / lines_total < 0.25 and all(order_flags)
            body = Body(paper.version_id, f"https://arxiv.org/pdf/{paper.version_id}", "pdf", sections, figures)
            _quality(body, int(self.config.get("min_chars", 2500)), order_ok=order_ok, missing_pages=missing)
            body.quality["physical_page_count"] = len(reader.pages)
            body.quality["missing_parts"] = [f"physical page {n}" for n in missing]
            body.quality["rotated_text_pages"] = rotated_pages
            body.quality["visual_page_requirements"] = rotated_pages
            if rotated_pages:
                body.quality["missing_parts"].append("Rotated labels may be absent from layout text; rendered page verification is required.")
            body.quality["reading_order_strategy"] = strategies
            body.quality["repeated_margin_lines_removed"] = len(repeated_edges)
            # Page-level headings provide a conservative mapping for the gate.
            # A PDF may have no HTML section tree, so headings are checked in
            # text too; this does not invent page numbers or rearrange text.
            located_headings = [(position, value) for position, raw in enumerate(page_lines) for line in raw.splitlines() if (value := _pdf_heading(line))]
            headings = [value for _, value in located_headings]
            heading_text = " ".join(headings)
            body.quality["detected_headings"] = headings
            body.quality["method_on_first_page"] = any(position == 0 and _METHOD.search(value) for position,value in located_headings)
            body.quality["evaluation_on_first_page"] = any(position == 0 and _EVALUATION.search(value) for position,value in located_headings)
            model_name = paper.title.split(":", 1)[0].strip().casefold()
            named_method = bool(model_name and any(model_name in heading.casefold() and re.search(r"\b(overall architecture|model architecture|proposed framework)\b", "\n".join(page_lines[position:position + 2]), re.I) for position, heading in located_headings))
            if _METHOD.search(heading_text) or named_method:
                body.quality["has_method"] = True
                body.quality["reasons"] = [r for r in body.quality["reasons"] if r != "method_section_missing"]
            if _EVALUATION.search(heading_text):
                body.quality["has_evaluation_or_theory"] = True
                body.quality["reasons"] = [r for r in body.quality["reasons"] if r != "evaluation_or_theory_section_missing"]
            if body.quality["has_method"] and body.quality["has_evaluation_or_theory"] and len(reader.pages) == 1:
                body.quality["reasons"] = [r for r in body.quality["reasons"] if r != "no_section_structure"]
            body.quality["passed"] = not body.quality["reasons"]
            return body
        except ProcessingError:
            raise
        except Exception:
            raise ProcessingError("pdf_parse_failed") from None
        finally:
            if pdfium_doc is not None:
                pdfium_doc.close()
            if reader is not None:
                reader.close()

    def _prepare_visuals(self, pdf_path: Path, paper: Paper, body: Body) -> None:
        pages = sorted({int(match.group(1)) for f in body.figures if f.required and (match := re.match(r"pdf-page:(\d+):caption:", f.locator))})
        pages = sorted(set(pages) | set(body.quality.get("visual_page_requirements",[])))
        if len(pages) > int(self.config.get("max_visual_pages", 8)):
            body.quality["passed"] = False
            body.quality["reasons"].append("critical_visual_pages_exceed_limit")
            return
        for number in pages:
            if not any(f.required and f.locator.startswith(f"pdf-page:{number}:caption:") for f in body.figures):
                # This is a derived reading requirement, not a fabricated
                # paper figure/caption. No source quote is supplied for it.
                body.figures.append(Figure(f"Physical page {number} visual verification",f"pdf-page:{number}:caption:visual_requirement","",required=True))
            target = self.work_dir / f"{paper.version_id.replace('/', '_')}-page-{number}.png"
            try:
                self.render_page(pdf_path, number, target)
            except Exception:
                body.quality["passed"] = False
                body.quality["reasons"].append("critical_visual_render_failed")
                return
            for figure in body.figures:
                if figure.required and figure.locator.startswith(f"pdf-page:{number}:caption:"):
                    figure.image_path = str(target)
        body.quality["rendered_physical_pages"] = pages

    def render_page(self, path: str | Path, page_number: int, output: str | Path, scale: float = 2.0) -> Path:
        """Render a needed physical PDF page for visual review or model input."""
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(str(path))
        try:
            if page_number < 1 or page_number > len(doc):
                raise ProcessingError("render_page_out_of_range")
            target = Path(output).resolve()
            if self.work_dir not in target.parents:
                raise ProcessingError("render_target_outside_work_dir")
            target.parent.mkdir(parents=True, exist_ok=True)
            page = doc.get_page(page_number - 1)
            try:
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    try:
                        image.save(target, format="PNG")
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()
            return target
        finally:
            doc.close()
