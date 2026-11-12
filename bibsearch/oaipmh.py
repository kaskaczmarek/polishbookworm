"""Wspólna baza dla serwisów z punktem OAI-PMH (FBC, Crispa).

OAI-PMH zwraca metadane Dublin Core — to pozwala zebrać opisy obiektów,
ale nie szukać fraz w treści. Adapter pobiera rekordy stronami i filtruje
lokalnie dopasowaniem przybliżonym (błędy OCR, dawna pisownia).

UWAGA (do weryfikacji z HAR): pełnotekstowe endpointy webowe FBC
(projekt FBC-TeNe) i Crispy nie są udokumentowane. Po ich odtworzeniu
z zapisu ruchu należy dodać dedykowane klasy Searcher; ta baza pozostanie
jako fallback metadanych.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Optional

from .base import AdapterError, BaseSearcher, Fetcher, SearchResult
from .normalize import fuzzy_contains

OAI_NS = "http://www.openarchives.org/OAI/2.0/"
DC_NS = "http://purl.org/dc/elements/1.1/"


class OaiPmhSearcher(BaseSearcher):
    name = "oaipmh"

    def __init__(
        self,
        endpoint: str,
        fetcher: Optional[Fetcher] = None,
        limit: int = 20,
        metadata_prefix: str = "oai_dc",
        phrase: Optional[str] = None,
    ):
        super().__init__(fetcher=fetcher, limit=limit)
        self.endpoint = endpoint
        self.metadata_prefix = metadata_prefix
        self.phrase = phrase

    def _list_records_url(self, **params: str) -> str:
        base = f"{self.endpoint}{'&' if '?' in self.endpoint else '?'}"
        joined = "&".join(f"{k}={v}" for k, v in params.items())
        return base + joined

    def _parse_records(self, raw: bytes) -> tuple[list[SearchResult], Optional[str]]:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise AdapterError(f"{self.name}: niepoprawny XML: {exc}") from exc
        error = root.find(f"{{{OAI_NS}}}error")
        if error is not None and error.get("code") not in (None, "noRecordsHierarchy", "noSetHierarchy"):
            raise AdapterError(f"{self.name}: błąd OAI-PMH: {error.get('code')}: {error.text}")
        results: list[SearchResult] = []
        token_el = root.find(f"{{{OAI_NS}}}ListRecords/{{{OAI_NS}}}resumptionToken")
        token = token_el.text if token_el is not None else None
        for rec in root.findall(f"{{{OAI_NS}}}ListRecords/{{{OAI_NS}}}record"):
            header = rec.find(f"{{{OAI_NS}}}header")
            metadata = rec.find(f"{{{OAI_NS}}}metadata")
            if metadata is None:
                continue

            def dc_get(tag: str) -> Optional[str]:
                el = metadata.find(f".//{{{DC_NS}}}{tag}")
                return el.text if el is not None and el.text else None

            if dc_get("title") is None:
                continue

            title = dc_get("title") or "(bez tytułu)"
            url = dc_get("identifier") or ""
            description = dc_get("description") or ""
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    source=self.name,
                    context=description[:300] or None,
                    extra={
                        "date": dc_get("date"),
                        "creator": dc_get("creator"),
                        "oai_identifier": header.findtext(f"{{{OAI_NS}}}identifier") if header is not None else None,
                    },
                )
            )
        return results, token

    def search(self, phrase: str, limit: Optional[int] = None) -> list[SearchResult]:
        """Filtruje rekordy OAI-PMH dopasowaniem przybliżonym do frazy."""
        limit = limit or self.limit
        matched: list[SearchResult] = []
        params = f"verb=ListRecords&metadataPrefix={self.metadata_prefix}"
        token: Optional[str] = None
        seen_ids: set[str] = set()
        while True:
            url = self._list_records_url(**dict(p.split("=", 1) for p in params.split("&")))
            raw = self.fetcher(url)
            records, new_token = self._parse_records(raw)
            for rec in records:
                key = rec.extra.get("oai_identifier") or rec.url
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                haystack = " ".join(filter(None, [rec.title, rec.context or ""]))
                if fuzzy_contains(haystack, phrase):
                    rec.context = _clip(rec.context, phrase)
                    matched.append(rec)
                    if len(matched) >= limit:
                        return matched
            token = new_token
            if not token:
                break
            params = f"verb=ListRecords&resumptionToken={token}"
        return matched


def _clip(context: Optional[str], phrase: str) -> Optional[str]:
    if not context:
        return None
    match = re.search(re.escape(phrase.split()[0]), context, re.IGNORECASE)
    if not match:
        return context[:200]
    start = max(0, match.start() - 60)
    return "…" + context[start : start + 180] + "…"
