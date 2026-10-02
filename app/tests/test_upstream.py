from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from arxivdaily.models import Paper
from arxivdaily.upstream import canonicalize_metadata, merge_metadata


STAMP = datetime(2026, 10, 1, tzinfo=timezone.utc)


def paper(version: int, *, authors: list[str], categories: list[str]) -> Paper:
    return Paper(
        version_id=f"2610.00001v{version}",
        title=f"Version {version}",
        abstract=f"Abstract for version {version}",
        categories=categories,
        published=STAMP.isoformat(),
        updated=(STAMP + timedelta(days=version)).isoformat(),
        authors=authors,
        pdf_url=f"https://arxiv.org/pdf/2610.00001v{version}",
    )


class UpstreamAdapterTests(unittest.TestCase):
    def test_normalizes_base_id_and_metadata_without_losing_version(self):
        original = paper(2, authors=["A", " A ", "B"], categories=["cs.CV", "cs.CV", "cs.AI"])
        normalized = canonicalize_metadata(original)
        self.assertEqual(normalized.base_id, "2610.00001")
        self.assertEqual(normalized.version_id, "2610.00001v2")
        self.assertEqual(normalized.authors, ["A", "B"])
        self.assertEqual(normalized.categories, ["cs.CV", "cs.AI"])

    def test_duplicate_merge_keeps_newest_version_and_cross_listings(self):
        old = paper(1, authors=["A"], categories=["cs.CV"])
        new = paper(2, authors=["B", "A"], categories=["cs.AI", "cs.CV"])
        merged = merge_metadata(old, new)
        self.assertEqual(merged.version_id, "2610.00001v2")
        self.assertEqual(merged.title, "Version 2")
        self.assertEqual(merged.abstract, "Abstract for version 2")
        self.assertEqual(merged.authors, ["B", "A"])
        self.assertEqual(merged.categories, ["cs.AI", "cs.CV"])

    def test_same_update_time_orders_versions_numerically(self):
        earlier = paper(9, authors=["A"], categories=["cs.CV"])
        later = paper(10, authors=["B"], categories=["cs.AI"])
        later.updated = earlier.updated
        merged = merge_metadata(later, earlier)
        self.assertEqual(merged.version_id, "2610.00001v10")
        self.assertEqual(merged.title, "Version 10")
        self.assertEqual(merged.categories, ["cs.AI", "cs.CV"])

    def test_old_style_id_remains_supported(self):
        item = paper(2, authors=["A"], categories=["hep-th", "cs.CV"])
        item.version_id = "hep-th/9901001v2"
        normalized = canonicalize_metadata(item)
        self.assertEqual(normalized.base_id, "hep-th/9901001")
        self.assertEqual(normalized.version_id, "hep-th/9901001v2")

    def test_rejects_merge_of_distinct_base_ids(self):
        other = paper(1, authors=["A"], categories=["cs.CV"])
        other.version_id = "2610.00002v1"
        with self.assertRaises(ValueError):
            merge_metadata(paper(1, authors=["A"], categories=["cs.CV"]), other)
