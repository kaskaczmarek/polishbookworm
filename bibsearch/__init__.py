"""bibsearch — wspólne wyszukiwanie w Polona 2, FBC i Crispie."""

from .adapters import CrispaSearcher, FbcSearcher
from .base import AdapterError, BaseSearcher, SearchResult
from .polona import PolonaSearcher

__all__ = [
    "AdapterError",
    "BaseSearcher",
    "SearchResult",
    "PolonaSearcher",
    "FbcSearcher",
    "CrispaSearcher",
]
__version__ = "0.1.0"
