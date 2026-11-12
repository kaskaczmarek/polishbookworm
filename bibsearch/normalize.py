"""Normalizacja tekstu: polskie znaki, dawna pisownia, tolerancja błędów OCR."""

from __future__ import annotations

import re
import unicodedata

_OLD_ORIGINAL_MAP = {
    "á": "a", "à": "a", "â": "a", "é": "e", "è": "e", "ê": "e",
    "í": "i", "ó": "o", "ú": "u", "ÿ": "y", "ō": "o",
    "ł": "l", "ø": "o", "đ": "d",
}

_OCR_CONFUSABLES = {
    "rn": "m", "cl": "d", "vv": "w", "1": "l", "0": "o",
}


def strip_diacritics(text: str) -> str:
    text = "".join(_OLD_ORIGINAL_MAP.get(ch, ch) for ch in text.lower())
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize(text: str) -> str:
    """Małe litery, bez diakrytyków, bez interpunkcji, zbitki błędów OCR."""
    text = strip_diacritics(text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    for src, dst in _OCR_CONFUSABLES.items():
        text = text.replace(src, dst)
    return text


def similarity(a: str, b: str) -> float:
    """Podobieństwo 0..1 (SequenceMatcher) dla fraz znormalizowanych."""
    from difflib import SequenceMatcher

    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def fuzzy_contains(haystack: str, needle: str, threshold: float = 0.85) -> bool:
    """Czy `needle` występuje w `haystack` z tolerancją błędów OCR.

    Sprawdzane są okna o długości frazy (w słowach) na wypadek rozjechanych
    długości po normalizacji.
    """
    hay_n, needle_n = normalize(haystack), normalize(needle)
    if not needle_n:
        return False
    if needle_n in hay_n:
        return True
    hay_words = hay_n.split()
    needle_words = needle_n.split()
    n = len(needle_words)
    if not hay_words or n == 0:
        return False
    for i in range(0, max(1, len(hay_words) - n + 1)):
        window = " ".join(hay_words[i : i + n])
        if similarity(window, needle_n) >= threshold:
            return True
    return False
