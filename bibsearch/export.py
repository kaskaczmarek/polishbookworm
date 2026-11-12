"""Deduplikacja i eksport wyników."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from .base import SearchResult
from .normalize import normalize


def dedup(results: list[SearchResult]) -> list[SearchResult]:
    """Usuwa duplikaty po URL oraz po znormalizowanym tytule (w obrębie źródła)."""
    seen_urls: set[str] = set()
    seen_titles: set[tuple[str, str]] = set()
    out: list[SearchResult] = []
    for r in results:
        url_key = r.url.rstrip("/")
        title_key = (r.source, normalize(r.title))
        if url_key in seen_urls or (r.url and title_key in seen_titles):
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        out.append(r)
    return out


def export_csv(results: list[SearchResult], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["source", "title", "url", "page", "context"])
        for r in results:
            writer.writerow([r.source, r.title, r.url, r.page or "", (r.context or "").replace("\n", " ")])


def export_json(results: list[SearchResult], path: str) -> None:
    payload = [
        {
            "source": r.source,
            "title": r.title,
            "url": r.url,
            "page": r.page,
            "context": r.context,
            "extra": r.extra,
        }
        for r in results
    ]
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export(results: list[SearchResult], spec: str) -> None:
    """spec: 'csv:plik.csv' albo 'json:plik.json'."""
    fmt, _, path = spec.partition(":")
    if not path:
        raise ValueError(f"zły format eksportu: {spec!r}; użyj csv:plik lub json:plik")
    if fmt == "csv":
        export_csv(results, path)
    elif fmt == "json":
        export_json(results, path)
    else:
        raise ValueError(f"nieznany format eksportu: {fmt}")
