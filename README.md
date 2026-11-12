# bibsearch

Wspólne wyszukiwanie pełnotekstowe w trzech polskich serwisach bibliotek cyfrowych:
**Polona 2**, **FBC** (Federacja Bibliotek Cyfrowych) i **Crispa** (biblioteka cyfrowa UW).

Czysty Python 3.10+, zero zależności zewnętrznych.

## Użycie

```bash
python3 -m bibsearch.cli "miłość ojczyzny" --limit 20
python3 -m bibsearch.cli "Dziady część" --source polona --source crispa
python3 -m bibsearch.cli "Mickiewicz" --source fbc --export csv:wyniki.csv
python3 -m bibsearch.cli "konrad wallenrod" --export json:wyniki.json --delay 2.0
```

Fraza w cudzysłowie jest przekazywana do silników bez zmian (frazy dokładne
obsługuje składnia danego serwisu, np. `"..."` w Polonie).

## Aplikacja webowa

```bash
python3 -m bibsearch.webapp            # http://127.0.0.1:8000
python3 -m bibsearch.webapp --port 8080
```

Serwer nasłuchuje tylko na `127.0.0.1` (bez zależności, czysty stdlib).
Endpointy:

- `/` — formularz z wyborem serwisów i wynikami,
- `/api/search?phrase=...&source=polona&source=fbc&limit=20` — JSON,
- `/export.csv?phrase=...&source=...`, `/export.json?...` — pobranie wyników.

## Architektura

Wspólny interfejs (`bibsearch/base.py`):

```python
class BaseSearcher:
    def search(self, phrase: str, limit: int | None = None) -> list[SearchResult]: ...
```

`SearchResult` zawiera: `title`, `url`, `source`, `page`, `context` (fragment
kontekstu), `score`, `extra` (metadane źródłowe).

Adaptery:

| Serwis | Plik | Mechanizm | Status |
|---|---|---|---|
| Polona 2 | `bibsearch/polona.py` | API JSON `api.polona.pl/api/search/` (to samo, z którego korzysta PyPolona) | działa na publicznym API; składnia zapytań w treści (OCR) do potwierdzenia z HAR |
| FBC | `bibsearch/adapters.py` | OAI-PMH + lokalne dopasowanie przybliżone metadanych | fallback metadanych; pełnotekstowy endpoint (FBC-TeNe) nieudokumentowany |
| Crispa (UW) | `bibsearch/adapters.py` | OAI-PMH `crispa.uw.edu.pl/complete/oai-pmh/v2` + lokalne dopasowanie | fallback metadanych; ukryte API webowe do odtworzenia z HAR |

## Obsługa typowych problemów

- **polskie znaki i dawna pisownia** (`bibsearch/normalize.py`): normalizacja
  usuwa diakrytyki i dawne grafemy (`é`, `á`, `ł`…),
- **błędy OCR**: dopasowanie przybliżone (`fuzzy_contains`) z typowymi
  pomyłkami (`rn`→`m`, `cl`→`d`, `vv`→`w`, `1`→`l`, `0`→`o`) i progiem
  podobieństwa,
- **deduplikacja**: po URL i znormalizowanym tytule w obrębie źródła,
- **eksport**: CSV (z BOM, otwiera się w Excelu) i JSON,
- **higiena zapytań**: czytelny `User-Agent`, konfigurowalne opóźnienie
  (`--delay`), wykrywanie zmian schematu odpowiedzi (`AdapterError`).

## Testy

Testy działają na zapisanych fixture'ach (`tests/fixtures/`) — w trakcie
rozwoju nie obciążają serwerów:

```bash
python3 -m unittest discover -s tests -v
```

## Do zrobienia po zapisie HAR (zakładka Network w przeglądarce)

1. **Polona**: uruchom wyszukiwanie w treści, zapisz żądanie i sprawdź,
   czy fraza trafia do `query` bez zmian, czy w innym polu/parametrze.
   W razie różnicy podmień `FULLTEXT_QUERY_TEMPLATE` w `bibsearch/polona.py`.
2. **FBC**: odtwórz JSON-owy endpoint wyszukiwania webowego (projekt FBC-TeNe)
   i dodaj dedykowaną klasę `FbcSearcher` w `bibsearch/adapters.py`
   (wzorzec: `PolonaSearcher`).
3. **Crispa**: analogicznie — ukryte API interfejsu webowego.

Każdy nowy adapter to jedna klasa z metodą `search()`; CLI podłącza się
przez słownik `SEARCHERS` w `bibsearch/cli.py`.

## Uwagi prawne i etyczne

- Nieudokumentowane endpointy mogą się zmienić — adaptery rzucają
  `AdapterError` zamiast zwracać śmieciowe dane.
- Ustaw `--delay` ≥ 1 s, nie uruchamiaj masowych zapytań bez zgody operatorów
  (BN, PCSS, BUW); przy większym projekcie warto napisać do nich o dostęp.
- Program wyszukujący jest zwykle bezproblemowy; hurtowe pobieranie treści
  chronionych prawem autorskim to osobna kwestia — nie robi tego `bibsearch`.
