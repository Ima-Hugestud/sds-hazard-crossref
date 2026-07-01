"""
cas.py
CAS Registry Number extraction, formatting normalization, and checksum
validation.

Generalizes the CAS handling originally built for prop65-sds-checker, with
one addition: prop65-sds-checker's CAS regex captured anything CAS-*shaped*
without verifying the check digit. Since this tool's matching engine treats
CAS as the primary, high-confidence key across twelve lists (not one), a
checksum validator is added so a plugin can distinguish "genuine CAS number"
from "CAS-shaped text that happens to appear in the document" (e.g. a
part number or date range that coincidentally matches the pattern).
"""

import re

# CAS Registry Number format: 2-7 digits, hyphen, 2 digits, hyphen, 1 check digit.
_CAS_PATTERN = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")

# Stray dash variants sometimes present in copy-pasted or OCR'd SDS text.
_DASH_VARIANTS = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2212]")


def extract_cas_numbers(text: str) -> list[str]:
    """
    Extract CAS-shaped numbers from text, in first-seen order, deduplicated.

    This returns candidates by *shape* only (matching the pattern), not by
    checksum validity — callers that need to distinguish a genuine CAS
    number from a coincidental shape match should additionally check
    `is_valid_cas_checksum()`. Keeping extraction shape-only (rather than
    silently dropping checksum failures) means a malformed-but-real CAS
    number in a poorly-formatted SDS is still surfaced for a human to look
    at, rather than disappearing.
    """
    seen: dict[str, None] = {}
    for match in _CAS_PATTERN.finditer(text):
        seen.setdefault(match.group(1), None)
    return list(seen)


def normalize_cas(raw: str) -> str | None:
    """
    Normalize a CAS number's formatting: strip whitespace, convert stray
    dash characters (en-dash, em-dash, minus sign, etc.) to a standard
    hyphen, and confirm it matches the CAS shape.

    Returns the normalized string, or None if `raw` doesn't match the CAS
    shape at all (this is a formatting normalizer, not a validator — for
    checksum validation use `is_valid_cas_checksum`).
    """
    if not raw:
        return None
    cleaned = _DASH_VARIANTS.sub("-", raw.strip())
    match = _CAS_PATTERN.fullmatch(cleaned)
    return match.group(1) if match else None


def is_valid_cas_checksum(cas: str) -> bool:
    """
    Validate a CAS number's check digit.

    Algorithm: concatenate the digits before the final hyphen, reverse
    them, multiply each digit by its 1-indexed position, sum, and take
    mod 10. That must equal the final (check) digit.

    Example: 7732-18-5 (water) -> digits "773218" minus check digit "5"
    leaves "77321"... concatenated groups "773218", reversed "812377",
    weighted sum = 8*1+1*2+2*3+3*4+7*5+7*6 = 105, 105 % 10 == 5. Valid.
    """
    parts = cas.split("-")
    if len(parts) != 3:
        return False
    body1, body2, check_str = parts
    if not (body1.isdigit() and body2.isdigit() and check_str.isdigit()):
        return False
    if len(check_str) != 1:
        return False

    digits = body1 + body2
    weighted_sum = sum(
        int(digit) * position
        for position, digit in enumerate(reversed(digits), start=1)
    )
    return weighted_sum % 10 == int(check_str)
