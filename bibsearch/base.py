"""Wspólny interfejs adapterów wyszukiwania."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional
import urllib.request
import urllib.error


USER_AGENT = "bibsearch/0.1 (badawcze wyszukiwanie pelnotekstowe; kontakt: lokalny uzytkownik)"


class AdapterError(RuntimeError):
    """Odpowiedź serwisu nie zgadza się z oczekiwanym schematem lub endpoint padł."""


@dataclass
class SearchResult:
    title: str
    url: str
    source: str
    page: Optional[str] = None
    context: Optional[str] = None
    score: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


Fetcher = Callable[[str], bytes]


def make_fetcher(timeout: int = 30, delay: float = 1.0) -> Fetcher:
    """Zwraca funkcję pobierającą URL z rozsądnym User-Agent i opóźnieniem."""

    state = {"last": 0.0}

    def fetch(url: str) -> bytes:
        wait = delay - (time.monotonic() - state["last"])
        if wait > 0 and state["last"] > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
        except urllib.error.HTTPError as exc:
            raise AdapterError(f"HTTP {exc.code} dla {url}") from exc
        except urllib.error.URLError as exc:
            raise AdapterError(f"brak połączenia dla {url}: {exc.reason}") from exc
        state["last"] = time.monotonic()
        return data

    return fetch


class BaseSearcher:
    """Baza dla adapterów: search(fraza) -> list[SearchResult]."""

    name: str = "base"

    def __init__(self, fetcher: Optional[Fetcher] = None, limit: int = 20):
        self.fetcher = fetcher or make_fetcher()
        self.limit = limit

    def search(self, phrase: str, limit: Optional[int] = None) -> list[SearchResult]:
        raise NotImplementedError

    def search_many(self, phrases: Iterable[str], limit: Optional[int] = None) -> list[SearchResult]:
        out: list[SearchResult] = []
        for phrase in phrases:
            out.extend(self.search(phrase, limit))
        return out
