"""Interfejs wiersza poleceń: bibsearch "fraza" --source polona --source fbc ..."""

from __future__ import annotations

import argparse
import sys

from .adapters import CrispaSearcher, FbcSearcher
from .base import AdapterError, BaseSearcher, make_fetcher
from .export import dedup, export
from .polona import PolonaSearcher

SEARCHERS: dict[str, type[BaseSearcher]] = {
    "polona": PolonaSearcher,
    "fbc": FbcSearcher,
    "crispa": CrispaSearcher,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bibsearch",
        description="Wyszukiwanie pełnotekstowe w Polona 2, FBC i Crispie (UW).",
    )
    parser.add_argument("phrase", help='szukana fraza; w cudzysłowie dla frazy dokładnej, np. "Dziady część"')
    parser.add_argument(
        "--source",
        action="append",
        choices=list(SEARCHERS),
        help="serwis do przeszukania (można podać wielokrotnie); domyślnie wszystkie",
    )
    parser.add_argument("--limit", type=int, default=20, help="maks. wyników na serwis")
    parser.add_argument("--delay", type=float, default=1.0, help="opóźnienie między zapytaniami (s)")
    parser.add_argument("--export", metavar="SPEC", help="eksport: csv:plik.csv lub json:plik.json")
    parser.add_argument("--no-dedup", action="store_true", help="wyłącz deduplikację wyników")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sources = args.source or list(SEARCHERS)
    results = []
    errors: list[str] = []
    for name in sources:
        cls = SEARCHERS[name]
        searcher = cls(fetcher=make_fetcher(delay=args.delay), limit=args.limit)
        try:
            results.extend(searcher.search(args.phrase, limit=args.limit))
        except AdapterError as exc:
            errors.append(str(exc))
    if not args.no_dedup:
        results = dedup(results)
    for r in results:
        line = f"[{r.source}] {r.title}"
        if r.context:
            line += f" — {r.context[:120]}"
        print(line)
        print(f"    {r.url}")
    if args.export:
        export(results, args.export)
        print(f"\nZapisano {len(results)} wyników do {args.export}", file=sys.stderr)
    for err in errors:
        print(f"OSTRZEŻENIE: {err}", file=sys.stderr)
    return 0 if results or not errors else 1


if __name__ == "__main__":
    sys.exit(main())
