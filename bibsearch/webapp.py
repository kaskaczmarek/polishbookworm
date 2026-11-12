"""Aplikacja webowa bibsearch — serwer HTTP na czystym stdlib (bez zależności).

Uruchomienie (domyślnie tylko localhost, port 8000):
    python3 -m bibsearch.webapp [--host 127.0.0.1] [--port 8000]

Endpointy:
    /                 — formularz wyszukiwania
    /api/search       — JSON: ?phrase=...&source=polona&source=fbc&limit=20
    /export.csv        — CSV: ?phrase=...&source=...
    /export.json       — JSON: ?phrase=...&source=...
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .adapters import CrispaSearcher, FbcSearcher
from .base import AdapterError, SearchResult, make_fetcher
from .export import dedup
from .polona import PolonaSearcher

SEARCHERS: dict[str, type] = {
    "polona": PolonaSearcher,
    "fbc": FbcSearcher,
    "crispa": CrispaSearcher,
}

PAGE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>bibsearch — Polona 2 · FBC · Crispa</title>
<style>
 body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
 h1 a {{ text-decoration: none; color: inherit }}
 form {{ display: flex; gap: .5rem; flex-wrap: wrap; }}
 input[type=text] {{ flex: 1; padding: .5rem; font-size: 1rem; min-width: 240px }}
 button {{ padding: .5rem 1rem; font-size: 1rem; cursor: pointer }}
 .sources {{ margin: .75rem 0 }}
 .result {{ border-bottom: 1px solid #ddd; padding: .75rem 0 }}
 .result h3 {{ margin: 0 0 .2rem; font-size: 1.05rem }}
 .meta {{ color: #666; font-size: .9rem }}
 .ctx {{ margin-top: .3rem; color: #333 }}
 .err {{ color: #b00; white-space: pre-wrap }}
 .links a {{ margin-right: 1rem }}
</style>
</head>
<body>
<h1>📖 <a href="/">bibsearch</a> <small style="font-weight:normal;font-size:.55em;color:#666">Polona 2 · FBC · Crispa (UW)</small></h1>
<form method="get" action="/">
 <input type="text" name="phrase" value="{phrase}" placeholder='Fraza, np. "miłość ojczyzny"' required>
 <button type="submit">Szukaj</button>
</form>
<div class="sources">
 {checkboxes}
</div>
{body}
</body>
</html>"""

RESULTS_HTML = """<p>Znaleziono {n} wynik(ów). <span class="links">
 <a href="/export.csv?{q}">pobierz CSV</a>
 <a href="/export.json?{q}">pobierz JSON</a></span></p>
{items}"""

ITEM_HTML = """<div class="result">
 <h3><a href="{url}" rel="noopener" target="_blank">{title}</a></h3>
 <div class="meta">[{source}]{meta}</div>
 {ctx}
</div>"""


def run_search(
    phrase: str, sources: list[str], limit: int = 20, fetcher=None
) -> tuple[list[SearchResult], list[str]]:
    """Wspólna logika: zwraca (wyniki, błędy)."""
    results: list[SearchResult] = []
    errors: list[str] = []
    for name in sources:
        cls = SEARCHERS[name]
        searcher = cls(fetcher=fetcher or make_fetcher(), limit=limit)
        try:
            results.extend(searcher.search(phrase, limit=limit))
        except AdapterError as exc:
            errors.append(str(exc))
    return dedup(results), errors


def render_page(
    phrase: str = "",
    checked: dict[str, bool] | None = None,
    results: list[SearchResult] | None = None,
    errors: list[str] | None = None,
    query: str = "",
) -> str:
    checked = checked or {name: True for name in SEARCHERS}
    checkboxes = " ".join(
        f'<label><input type="checkbox" name="source" value="{n}"'
        f'{" checked" if checked.get(n) else ""}> {n}</label>'
        for n in SEARCHERS
    )
    body = ""
    if errors:
        body += "".join(f'<p class="err">OSTRZEŻENIE: {e}</p>' for e in errors)
    if results is not None:
        items = "".join(
            ITEM_HTML.format(
                url=r.url,
                title=_escape(r.title),
                source=r.source,
                meta=_meta(r),
                ctx=f'<div class="ctx">{_escape(r.context or "")}</div>' if r.context else "",
            )
            for r in results
        )
        body += RESULTS_HTML.format(n=len(results), q=query, items=items)
    return PAGE.format(phrase=_escape(phrase), checkboxes=checkboxes, body=body)


def _meta(r: SearchResult) -> str:
    parts = []
    if r.extra.get("year"):
        parts.append(str(r.extra["year"]))
    if r.extra.get("date"):
        parts.append(str(r.extra["date"]))
    if r.extra.get("creator"):
        parts.append(str(r.extra["creator"]))
    return f" — {'; '.join(parts)}" if parts else ""


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


class BibsearchHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        phrase = (params.get("phrase") or [""])[0].strip()
        sources = params.get("source") or list(SEARCHERS)
        sources = [s for s in sources if s in SEARCHERS]
        limit = min(int((params.get("limit") or ["20"])[0]), 100)

        if parsed.path == "/" and not phrase:
            self._html(render_page())
            return
        if parsed.path in ("/", "/api/search", "/export.csv", "/export.json") and phrase:
            results, errors = run_search(phrase, sources, limit)
            if parsed.path == "/api/search":
                self._json(
                    {
                        "results": [
                            {
                                "source": r.source,
                                "title": r.title,
                                "url": r.url,
                                "context": r.context,
                                "extra": r.extra,
                            }
                            for r in results
                        ],
                        "errors": errors,
                    }
                )
            elif parsed.path == "/export.csv":
                import csv
                import io

                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(["source", "title", "url", "context"])
                for r in results:
                    writer.writerow([r.source, r.title, r.url, (r.context or "").replace("\n", " ")])
                self._send(200, "text/csv; charset=utf-8", buf.getvalue().encode("utf-8-sig"))
            elif parsed.path == "/export.json":
                self._send(
                    200,
                    "application/json; charset=utf-8",
                    json.dumps(
                        [r.__dict__ for r in results], ensure_ascii=False, indent=2, default=str
                    ).encode("utf-8"),
                )
            else:
                q = urllib.parse.urlencode({"phrase": phrase, "source": sources}, doseq=True)
                self._html(render_page(phrase, {s: True for s in sources}, results, errors, q))
            return
        self._send(404, "text/plain; charset=utf-8", b"404")

    def _html(self, body: str) -> None:
        self._send(200, "text/html; charset=utf-8", body.encode("utf-8"))

    def _json(self, payload: dict) -> None:
        self._send(200, "application/json; charset=utf-8", json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _send(self, code: int, ctype: str, data: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[webapp] {self.address_string()} {fmt % args}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bibsearch-webapp", description="Webowy interfejs bibsearch")
    parser.add_argument("--host", default="127.0.0.1", help="domyślnie 127.0.0.1 (tylko localhost)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), BibsearchHandler)
    print(f"bibsearch webapp: http://{args.host}:{args.port} (Ctrl+C aby zakończyć)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
