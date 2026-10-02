"""High-recall metadata rules. They do not decide final relevance."""
from __future__ import annotations

import re
import unicodedata

from .models import Paper


_DASH = re.compile(r"[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D-]")
_SPACE = re.compile(r"\s+")


def _normal(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _DASH.sub(" ", text)
    return _SPACE.sub(" ", text).strip()


def _contains(text: str, phrase: str) -> bool:
    needle = _normal(phrase)
    if not needle:
        return False
    # Word boundaries on both ends also protect short acronyms such as CT and RL.
    return re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", text) is not None


def match_rules(paper: Paper, config: dict) -> list[str]:
    """Return all matching route names, in configured order, once each.

    Categories are an OR over *all* cross listings. The title is excluded from
    keyword matching unless explicitly enabled. Exclusion phrases use the same
    selected metadata field(s); body text is never searched here.
    """
    rules = config["rules"]
    categories = set(rules.get("categories", []))
    if categories and not categories.intersection(paper.categories):
        return []
    text = _normal(paper.abstract)
    if rules.get("title_enabled", False):
        text += " " + _normal(paper.title)
    if any(_contains(text, phrase) for phrase in rules.get("exclude", [])):
        return []
    hits = {
        name: any(_contains(text, phrase) for phrase in phrases)
        for name, phrases in rules["groups"].items()
    }
    return [
        name for name, clauses in rules["routes"].items()
        if any(all(hits[group] for group in clause) for clause in clauses)
    ]
