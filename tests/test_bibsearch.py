import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bibsearch.adapters import CrispaSearcher, FbcSearcher
from bibsearch.base import AdapterError, SearchResult, make_fetcher
from bibsearch.cli import main
from bibsearch.export import dedup, export
from bibsearch.normalize import fuzzy_contains, normalize, similarity
from bibsearch.polona import PolonaSearcher

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_fetcher(path: Path):
    data = path.read_bytes()

    def fetch(url):
        return data

    return fetch


class NormalizeTests(unittest.TestCase):
    def test_strip_diacritics(self):
        self.assertEqual(normalize("Żółć ĄĘÓ"), "zolc aeo")

    def test_old_orthography(self):
        self.assertEqual(normalize("czém"), "czem")

    def test_ocr_rn_m(self):
        self.assertTrue(fuzzy_contains("rnickiewicz", "Mickiewicz"))

    def test_fuzzy_contains_clean(self):
        self.assertTrue(fuzzy_contains("Pan Tadeusz z Litwy", "pan tadeusz"))
        self.assertFalse(fuzzy_contains("Podróże po Afryce", "pan tadeusz"))

    def test_similarity_order(self):
        self.assertGreater(similarity("Mickiewicz", "Mickiewicz"), similarity("Mickiewicz", "Sienkiewicz"))


class PolonaTests(unittest.TestCase):
    def test_search_parses_items(self):
        searcher = PolonaSearcher(fetcher=fixture_fetcher(FIXTURES / "polona_search.json"))
        results = searcher.search("mickiewicz")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "Pan Tadeusz, czyli Ostatni zajazd na Litwie")
        self.assertEqual(results[0].url, "https://polona.pl/item/pan-tadeusz,12345")
        self.assertEqual(results[0].source, "polona")
        self.assertTrue(results[0].extra["has_text_content"])

    def test_search_detects_bad_schema(self):
        def fetch(url):
            return b'{"unexpected": true}'

        searcher = PolonaSearcher(fetcher=fetch)
        with self.assertRaises(AdapterError):
            searcher.search("mickiewicz")


class OaiPmhTests(unittest.TestCase):
    def test_fbc_fuzzy_match(self):
        searcher = FbcSearcher(fetcher=fixture_fetcher(FIXTURES / "oaipmh_fbc.xml"))
        results = searcher.search("miłość ojczyzny")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Liryki i epigramata")
        self.assertIn("miłości ojczyzny", results[0].context)

    def test_fbc_no_match(self):
        searcher = FbcSearcher(fetcher=fixture_fetcher(FIXTURES / "oaipmh_fbc.xml"))
        self.assertEqual(searcher.search("kwantowa mechanika"), [])

    def test_crispa_endpoint(self):
        searcher = CrispaSearcher(fetcher=fixture_fetcher(FIXTURES / "oaipmh_fbc.xml"))
        self.assertIn("crispa.uw.edu.pl", searcher.endpoint)

    def test_oai_error(self):
        def fetch(url):
            return b'<?xml version="1.0"?><OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><error code="badVerb">zle</error></OAI-PMH>'

        searcher = FbcSearcher(fetcher=fetch)
        with self.assertRaises(AdapterError):
            searcher.search("cokolwiek")


class ExportTests(unittest.TestCase):
    def test_dedup_by_url_and_title(self):
        a = SearchResult(title="Pan Tadeusz", url="https://x/1", source="polona")
        b = SearchResult(title="Pan Tadeusz", url="https://x/1/", source="polona")
        c = SearchResult(title="PAN TADEUSZ!", url="https://x/2", source="polona")
        d = SearchResult(title="Pan Tadeusz", url="https://y/1", source="fbc")
        out = dedup([a, b, c, d])
        self.assertEqual([r.url for r in out], ["https://x/1", "https://y/1"])

    def test_export_csv_and_json(self):
        r = SearchResult(title="Tytuł", url="https://x/1", source="polona", context="frag,ment")
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "out.csv"
            json_path = Path(tmp) / "out.json"
            export([r], f"csv:{csv_path}")
            export([r], f"json:{json_path}")
            self.assertIn("Tytuł", csv_path.read_text(encoding="utf-8-sig"))
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data[0]["title"], "Tytuł")

    def test_export_bad_format(self):
        with self.assertRaises(ValueError):
            export([], "xml:plik.xml")


class CliTests(unittest.TestCase):
    def test_main_polona_only(self):
        with mock.patch("bibsearch.cli.SEARCHERS", {"polona": PolonaSearcher}):
            with mock.patch("bibsearch.cli.make_fetcher", lambda delay: fixture_fetcher(FIXTURES / "polona_search.json")):
                rc = main(["mickiewicz", "--source", "polona"])
        self.assertEqual(rc, 0)

    def test_main_adapter_error_reported(self):
        def fetch(url):
            raise AdapterError("HTTP 500 dla https://x")

        with mock.patch("bibsearch.cli.SEARCHERS", {"polona": PolonaSearcher}):
            with mock.patch("bibsearch.cli.make_fetcher", lambda delay: fetch):
                rc = main(["mickiewicz", "--source", "polona"])
        self.assertEqual(rc, 1)


class FetcherTests(unittest.TestCase):
    def test_fetcher_sets_user_agent(self):
        seen = {}

        def fake_urlopen(req, timeout):
            seen["ua"] = req.headers.get("User-agent")
            return mock.Mock()

        with mock.patch("bibsearch.base.urllib.request.urlopen", fake_urlopen):
            fetcher = make_fetcher(delay=0.0)
            with self.assertRaises(Exception):
                fetcher("https://example.invalid/")
        self.assertIn("bibsearch", seen.get("ua", ""))


if __name__ == "__main__":
    unittest.main()
