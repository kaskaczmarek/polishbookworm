"""Adapter Polona 2 (api.polona.pl) — publiczne API JSON używane też przez PyPolona.

UWAGA (do weryfikacji z HAR): składnia zapytań pełnotekstowych (OCR) nie ma
oficjalnej dokumentacji. Adapter przekazuje frazę bez zmian w `query`;
jeśli analiza ruchu wykaże inny parametr (np. pole `body:`), wystarczy
podmienić `FULLTEXT_QUERY_TEMPLATE`.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Optional

from .base import AdapterError, BaseSearcher, Fetcher, SearchResult

API_BASE = "https://api.polona.pl/api/search/"
ITEM_URL = "https://polona.pl/item/{slug},{id}"
FULLTEXT_QUERY_TEMPLATE = "{phrase}"


class PolonaSearcher(BaseSearcher):
    name = "polona"

    def __init__(self, fetcher: Optional[Fetcher] = None, limit: int = 20):
        super().__init__(fetcher=fetcher, limit=limit)

    def _build_url(self, phrase: str, limit: int, offset: int) -> str:
        query = FULLTEXT_QUERY_TEMPLATE.format(phrase=phrase)
        params = urllib.parse.urlencode({"query": query, "limit": limit, "offset": offset})
        return f"{API_BASE}?{params}"

    def search(self, phrase: str, limit: Optional[int] = None) -> list[SearchResult]:
        limit = limit or self.limit
        url = self._build_url(phrase, limit, 0)
        raw = self.fetcher(url)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AdapterError(f"Polona: nie-JSON odpowiedź: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise AdapterError(
                "Polona: nieoczekiwany schemat odpowiedzi (brak 'items'); "
                "endpoint mógł się zmienić"
            )
        results: list[SearchResult] = []
        for item in payload["items"]:
            if not isinstance(item, dict):
                raise AdapterError("Polona: element 'items' nie jest obiektem")
            item_id = item.get("id")
            slug = item.get("slug") or ""
            if item_id is None:
                continue
            results.append(
                SearchResult(
                    title=str(item.get("title") or "(bez tytułu)"),
                    url=ITEM_URL.format(slug=slug, id=item_id),
                    source=self.name,
                    context=", ".join(str(a) for a in (item.get("creators") or [])) or None,
                    score=None,
                    extra={
                        "language": item.get("language"),
                        "year": item.get("year"),
                        "has_text_content": item.get("has_text_content"),
                        "id": item_id,
                    },
                )
            )
        return results
