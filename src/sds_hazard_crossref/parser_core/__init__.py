"""
parser_core — shared SDS ingestion layer.

This package is the generalized extraction of the parsing logic originally
built for the sibling project `prop65-sds-checker`: PDF/text ingestion,
GHS section splitting, and CAS number handling. It is intentionally free of
any single hazard list's matching logic (Prop 65, NIOSH, etc.) — that lives
in the plugin layer (see `sds_hazard_crossref.plugins`) and, for Prop 65
specifically, in `prop65-sds-checker` itself.

Public API:
    SDSDocument        - parsed SDS with per-section text access
    extract_sds(path)  - open a PDF and return an SDSDocument
    extract_cas_numbers(text)  - find all CAS-shaped numbers in text
    normalize_cas(raw)         - normalize formatting; validate checksum
    normalize_name(raw)        - case-fold / whitespace-normalize a chemical name
"""

from .sds_document import SDSDocument, extract_sds
from .cas import extract_cas_numbers, normalize_cas, is_valid_cas_checksum
from .names import normalize_name

__all__ = [
    "SDSDocument",
    "extract_sds",
    "extract_cas_numbers",
    "normalize_cas",
    "is_valid_cas_checksum",
    "normalize_name",
]
