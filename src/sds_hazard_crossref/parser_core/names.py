"""
names.py
Chemical name normalization for the name-based fallback matcher (used only
when a component has no CAS number — see PROJECT_SPEC.md Section 7).

Deliberately conservative: this normalizes *text formatting* only (case,
whitespace, punctuation, unicode form). It does NOT strip salt or hydrate
notation (e.g. "sodium", "hydrate", "monohydrate") from a name, because
doing so can silently conflate chemically distinct substances that happen
to share a base name but have different CAS numbers and different hazard
profiles (e.g. a free acid vs. its sodium salt). Collapsing those together
in the name-matching layer would be exactly the kind of "forced low
confidence match" the project spec says to avoid.

Genuine name variants for the *same* substance (e.g. "MEK", "Methyl Ethyl
Ketone", "2-Butanone" — all CAS 78-93-3) are handled by an explicit,
human-curated synonym table in the matching engine, not by algorithmic
stripping here. That keeps every name-based match traceable to a specific,
reviewable equivalence someone actually asserted, rather than a heuristic
that could quietly merge two different chemicals.
"""

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_EDGE_PUNCT = re.compile(r"^[\s.,;:\-]+|[\s.,;:\-]+$")


def normalize_name(raw: str) -> str:
    """
    Normalize a chemical name for comparison: Unicode NFKC normalization,
    case-fold, collapse internal whitespace, strip leading/trailing
    punctuation. Does not alter chemical meaning (see module docstring).
    """
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", raw)
    text = text.casefold()
    text = _WHITESPACE.sub(" ", text).strip()
    text = _EDGE_PUNCT.sub("", text)
    return text
