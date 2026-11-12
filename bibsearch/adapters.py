"""Adaptery FBC i Crispa (biblioteka cyfrowa UW) oparte o OAI-PMH."""

from __future__ import annotations

from typing import Optional

from .base import Fetcher
from .oaipmh import OaiPmhSearcher

# Endpointy do potwierdzenia u operatorów / w HAR:
#  - FBC: punkt OAI-PMH agregatora (domyślnie zgodny z opisem protokołu).
#  - Crispa: podany punkt Dublin Core (crispa.uw.edu.pl/complete/oai-pmh/v2).
FBC_OAI_ENDPOINT = "https://www.fbc.pionier.net.pl/oai-pmh"
CRISPA_OAI_ENDPOINT = "https://crispa.uw.edu.pl/complete/oai-pmh/v2"


class FbcSearcher(OaiPmhSearcher):
    name = "fbc"

    def __init__(self, fetcher: Optional[Fetcher] = None, limit: int = 20, endpoint: str = FBC_OAI_ENDPOINT):
        super().__init__(endpoint=endpoint, fetcher=fetcher, limit=limit)


class CrispaSearcher(OaiPmhSearcher):
    name = "crispa"

    def __init__(self, fetcher: Optional[Fetcher] = None, limit: int = 20, endpoint: str = CRISPA_OAI_ENDPOINT):
        super().__init__(endpoint=endpoint, fetcher=fetcher, limit=limit)
