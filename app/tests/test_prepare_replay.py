from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from arxivdaily.models import Paper
from scripts.prepare_replay import REPLAY_IDS, prepare_replay


STAMP = datetime(2026, 10, 1, tzinfo=timezone.utc).isoformat()
TEST_TMP = Path(__file__).resolve().parents[1] / "tmp" / "tests"
TEST_TMP.mkdir(parents=True, exist_ok=True)


class FakeCollector:
    def __init__(self, versions):
        self.versions = versions
        self.requested = None

    def by_ids(self, identifiers):
        self.requested = tuple(identifiers)
        return [Paper(version, f"Paper {version}", "Synthetic abstract.", ["cs.CV"], STAMP, STAMP) for version in self.versions]


class Response:
    def __init__(self, data, content_type, url):
        self.data = data
        self.headers = {"Content-Type": content_type}
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size):
        return self.data[:size]

    def geturl(self):
        return self.url


class ReplayTests(unittest.TestCase):
    def test_pinned_sources_and_hash_manifest(self):
        calls = []

        def opener(request, timeout):
            url = request.full_url
            calls.append(url)
            if url.endswith("html/2603.19169v1"):
                raise HTTPError(url, 404, "not converted", {}, None)
            if "/html/" in url:
                return Response(b"<!doctype html><html><body>paper</body></html>", "text/html", url)
            return Response(b"%PDF-1.7\nsynthetic source", "application/pdf", url)

        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temp:
            collector = FakeCollector(REPLAY_IDS)
            manifest = prepare_replay(Path(temp), collector=collector, opener=opener, min_interval=0)
            self.assertEqual(collector.requested, REPLAY_IDS)
            self.assertEqual(len(manifest["papers"]), 4)
            self.assertEqual(len(calls), 8)
            self.assertEqual([len(item["sources"]) for item in manifest["papers"]], [2, 2, 2, 1])
            pdf = Path(temp) / "2308.00692v3.pdf"
            self.assertEqual(manifest["papers"][0]["sources"][1]["sha256"], hashlib.sha256(pdf.read_bytes()).hexdigest())
            saved = json.loads((Path(temp) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["schema_version"], 2)
            self.assertTrue(saved["complete"])

    def test_metadata_version_mismatch_stops_before_download(self):
        def no_network(*args, **kwargs):
            self.fail("source download should not start")

        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temp:
            wrong = list(REPLAY_IDS)
            wrong[0] = "2308.00692v2"
            with self.assertRaisesRegex(ValueError, "version mismatch"):
                prepare_replay(Path(temp), collector=FakeCollector(wrong), opener=no_network, min_interval=0)
            self.assertFalse((Path(temp) / "manifest.json").exists())

    def test_timeout_preserves_metadata_and_completed_source_then_resumes(self):
        calls = []

        def first_opener(request, timeout):
            url = request.full_url
            calls.append(url)
            if url.endswith("pdf/2308.00692v3"):
                raise TimeoutError("synthetic read timeout")
            if "/html/" in url:
                return Response(b"<html>saved</html>", "text/html", url)
            return Response(b"%PDF-1.7\nbody", "application/pdf", url)

        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temp:
            output = Path(temp)
            first = prepare_replay(output, collector=FakeCollector(REPLAY_IDS), opener=first_opener, min_interval=0, attempts=1)
            self.assertFalse(first["complete"])
            self.assertEqual(first["papers"][0]["failures"][0]["error"], "TimeoutError")
            self.assertEqual(len(first["papers"]), 4)
            saved_html = output / "2308.00692v3.html"
            digest = hashlib.sha256(saved_html.read_bytes()).hexdigest()
            saved_manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved_manifest["papers"][0]["metadata"]["version_id"], "2308.00692v3")
            self.assertEqual(saved_manifest["papers"][0]["sources"][0]["sha256"], digest)

            resumed_calls = []

            def second_opener(request, timeout):
                resumed_calls.append(request.full_url)
                return Response(b"%PDF-1.7\nrecovered", "application/pdf", request.full_url)

            class NoMetadataCollector:
                def by_ids(self, identifiers):
                    raise AssertionError("cached metadata should avoid another API request")

            second = prepare_replay(output, collector=NoMetadataCollector(), opener=second_opener, min_interval=0)
            self.assertTrue(second["complete"])
            self.assertEqual(resumed_calls, ["https://arxiv.org/pdf/2308.00692v3"])
            self.assertEqual(hashlib.sha256(saved_html.read_bytes()).hexdigest(), digest)

    def test_existing_html_without_manifest_is_reused(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temp:
            output = Path(temp)
            (output / "2308.00692v3.html").write_bytes(b"<html>prior run</html>")
            calls = []

            def opener(request, timeout):
                calls.append(request.full_url)
                if "/html/" in request.full_url:
                    return Response(b"<html>fresh</html>", "text/html", request.full_url)
                return Response(b"%PDF-1.7\nbody", "application/pdf", request.full_url)

            result = prepare_replay(output, collector=FakeCollector(REPLAY_IDS), opener=opener, min_interval=0)
            self.assertTrue(result["complete"])
            self.assertNotIn("https://arxiv.org/html/2308.00692v3", calls)
            self.assertEqual((output / "2308.00692v3.html").read_bytes(), b"<html>prior run</html>")

    def test_transient_read_error_retries_with_finite_attempts(self):
        retries = 0

        def opener(request, timeout):
            nonlocal retries
            url = request.full_url
            if url.endswith("pdf/2308.00692v3") and retries < 2:
                retries += 1
                raise TimeoutError("synthetic read timeout")
            if "/html/" in url:
                return Response(b"<html>paper</html>", "text/html", url)
            return Response(b"%PDF-1.7\nbody", "application/pdf", url)

        with tempfile.TemporaryDirectory(dir=TEST_TMP) as temp:
            manifest = prepare_replay(Path(temp), collector=FakeCollector(REPLAY_IDS), opener=opener, min_interval=0, attempts=3, backoff_seconds=0)
            self.assertEqual(retries, 2)
            self.assertTrue(manifest["complete"])
            self.assertEqual(manifest["papers"][0]["failures"], [])


if __name__ == "__main__":
    unittest.main()
