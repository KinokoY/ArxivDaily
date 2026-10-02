"""Narrow adapter for the pinned Paper Digest metadata utilities.

The upstream package is loaded under a private name so an unrelated installed
``paper_digest`` distribution cannot silently replace the vendored revision.
Its API/RSS fetcher is deliberately not used: collection uses arxiv.py 4.x.
"""
from __future__ import annotations

from dataclasses import replace
from importlib import import_module, util
from pathlib import Path
import re
import sys
from types import ModuleType

from .models import Paper, ProcessingError, parse_time


_PACKAGE_NAME = "_arxivdaily_pinned_paper_digest"
_PACKAGE_DIR = Path(__file__).resolve().parent / "_vendor" / "paper_digest"


def _upstream_arxiv_client() -> ModuleType:
    if _PACKAGE_NAME not in sys.modules:
        specification = util.spec_from_file_location(
            _PACKAGE_NAME,
            _PACKAGE_DIR / "__init__.py",
            submodule_search_locations=[str(_PACKAGE_DIR)],
        )
        if specification is None or specification.loader is None:
            raise RuntimeError("pinned Paper Digest source is unavailable")
        package = util.module_from_spec(specification)
        sys.modules[_PACKAGE_NAME] = package
        try:
            specification.loader.exec_module(package)
        except BaseException:
            sys.modules.pop(_PACKAGE_NAME, None)
            raise
    return import_module(f"{_PACKAGE_NAME}.arxiv_client")


def _metadata(paper: Paper):
    upstream_paper = _upstream_arxiv_client().Paper(
        title=paper.title,
        summary=paper.abstract,
        authors=paper.authors,
        categories=paper.categories,
        paper_id=paper.url,
        abstract_url=paper.url,
        pdf_url=paper.pdf_url or None,
        published_at=parse_time(paper.published),
        updated_at=parse_time(paper.updated),
    )
    if upstream_paper.canonical_id() != f"arxiv:{paper.base_id}":
        raise ProcessingError("upstream arXiv identity disagrees with pinned paper ID")
    return upstream_paper


def canonicalize_metadata(paper: Paper) -> Paper:
    """Reuse upstream ID and ordered metadata normalization for one result.

    ArxivDaily remains authoritative for the version ID and timestamps.
    """
    normalized = _metadata(paper)
    return replace(paper, authors=normalized.authors, categories=normalized.categories)


def merge_metadata(existing: Paper, incoming: Paper) -> Paper:
    """Merge cross-listing metadata via upstream's ``Paper.merge_duplicate``.

    The newest version's content and ID win; the upstream merge contributes
    unique authors and categories from every encounter of that base ID.
    """
    if existing.base_id != incoming.base_id:
        raise ValueError("cannot merge different arXiv base IDs")
    first, second = _metadata(existing), _metadata(incoming)
    first.merge_duplicate(second)
    newest = max(
        (existing, incoming),
        key=lambda item: (
            parse_time(item.updated),
            int(match.group(1)) if (match := re.search(r"v([1-9]\d*)$", item.version_id)) else 0,
        ),
    )
    return replace(
        newest,
        authors=first.authors,
        categories=first.categories,
        pdf_url=newest.pdf_url or first.pdf_url or "",
    )
