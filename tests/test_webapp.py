import unittest
from pathlib import Path

from bibsearch.webapp import BibsearchHandler, render_page, run_search

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_fetcher(path: Path):
    data = path.read_bytes()

    def fetch(url):
        return data

    return fetch


class RenderTests(unittest.TestCase):
    def test_empty_page_has_form_and_sources(self):
        html = render_page()
        self.assertIn('name="phrase"', html)
        for src in ("polona", "fbc", "crispa"):
            self.assertIn(f'value="{src}"', html)

    def test_results_page_escapes_and_links(self):
        html = render_page(
            "fraza",
            results=[
                type(
                    "R",
                    (),
                    {
                        "title": "Pan <Tadeusz>",
                        "url": "https://polona.pl/item/x,1",
                        "source": "polona",
                        "context": 'Cytat "zawierający" znaki',
                        "extra": {"year": 1834, "creator": "A. Mickiewicz"},
                    },
                )()
            ],
        )
        self.assertIn("Pan &lt;Tadeusz&gt;", html)
        self.assertIn("https://polona.pl/item/x,1", html)
        self.assertIn("1834", html)
        self.assertIn("A. Mickiewicz", html)
        self.assertIn("pobierz CSV", html)

    def test_errors_rendered(self):
        html = render_page(errors=["HTTP 500 dla https://x"])
        self.assertIn("HTTP 500", html)


class RunSearchTests(unittest.TestCase):
    def test_polona_fixture(self):
        results, errors = run_search(
            "mickiewicz", ["polona"], fetcher=fixture_fetcher(FIXTURES / "polona_search.json")
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].source, "polona")

    def test_bad_source_filtered_by_handler(self):
        results, errors = run_search(
            "mickiewicz", ["fbc"], fetcher=fixture_fetcher(FIXTURES / "oaipmh_fbc.xml")
        )
        self.assertEqual(len(results), 0)
        self.assertEqual(errors, [])


class HandlerTests(unittest.TestCase):
    def _request(self, path):
        handler = BibsearchHandler.__new__(BibsearchHandler)
        sent = {}

        def send_response(code):
            sent["code"] = code

        def send_header(k, v):
            sent.setdefault("headers", {})[k] = v

        handler.send_response = send_response
        handler.send_header = send_header
        handler.end_headers = lambda: None
        class W:
            def write(self_, data):
                sent.setdefault("data", data)

        handler.wfile = W()
        handler.path = path
        return handler, sent

    def test_404_for_unknown_path(self):
        handler, sent = self._request("/nie-znane")
        handler.do_GET()
        self.assertEqual(sent["code"], 404)

    def test_home_without_phrase(self):
        handler, sent = self._request("/")
        handler.do_GET()
        self.assertEqual(sent["code"], 200)
        self.assertIn(b'name="phrase"', sent["data"])


if __name__ == "__main__":
    unittest.main()
