"""
composition.py
Extracts structured component rows (name, CAS, concentration) from an SDS's
Section 3 (Composition/Information on Ingredients) text.

This is a best-effort, heuristic parser. PDF text extraction destroys real
table structure — a Section 3 table becomes a flat sequence of lines with
inconsistent spacing, and manufacturers format this section in dozens of
different column orders and phrasings. This parser makes a reasonable
attempt per line and flags anything it can't confidently interpret rather
than guessing. It is expected to need refinement against a wider corpus of
real SDS documents over time (see PROJECT_SPEC.md Section 3: OCR/scanned
PDFs are explicitly out of scope for v1 and should be flagged the same way).
"""

import re
from dataclasses import dataclass

from .cas import extract_cas_numbers

_PERCENT_PATTERN = re.compile(
    r"(<\s*\d{1,3}(?:\.\d+)?\s*%|\d{1,3}(?:\.\d+)?\s*-\s*\d{1,3}(?:\.\d+)?\s*%|\d{1,3}(?:\.\d+)?\s*%)"
)

# Lines that are column headers, not data rows — skip these rather than
# treating "Chemical Name" or "CAS Number" as a component.
_HEADER_LINE = re.compile(
    r"^\s*(chemical\s+name|component|ingredient)s?\b.*\b(cas|concentration|%)",
    re.IGNORECASE,
)

# Signals a manufacturer is withholding the identity as trade secret / CBI,
# per OSHA HazCom's trade-secret provision. When present with no CAS
# disclosed, this must be flagged as unresolvable — never guessed.
_TRADE_SECRET_MARKERS = re.compile(
    r"\b(proprietary|trade\s+secret|confidential\s+business\s+information|\bCBI\b|withheld)\b",
    re.IGNORECASE,
)

_SECTION_TITLE_LINE = re.compile(r"^\s*SECTION\s+3\b", re.IGNORECASE)


@dataclass
class Component:
    raw_name: str
    raw_cas: str | None
    concentration_range: str | None
    # "cas_disclosed" | "trade_secret" | "no_cas_disclosed"
    disclosure_type: str


def extract_components(composition_text: str) -> list[Component]:
    """
    Parse Section 3 text into a list of Component rows.

    Only lines containing at least a plausible chemical name are kept:
    header rows, the section title line, and blank lines are skipped.
    A line with no CAS number is still captured (as `no_cas_disclosed` or
    `trade_secret`, depending on whether trade-secret language is present)
    rather than dropped, so the matching engine can flag it for manual
    follow-up instead of silently under-reporting the product's contents.
    """
    components: list[Component] = []

    for line in composition_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _SECTION_TITLE_LINE.match(stripped):
            continue
        if _HEADER_LINE.match(stripped):
            continue

        cas_matches = extract_cas_numbers(stripped)
        raw_cas = cas_matches[0] if cas_matches else None

        percent_match = _PERCENT_PATTERN.search(stripped)
        concentration_range = percent_match.group(1) if percent_match else None

        # A line needs at least a CAS number or a concentration figure to be
        # treated as a component row — otherwise it's very likely prose
        # (a use-restriction note, a footnote) rather than a table row.
        if raw_cas is None and concentration_range is None:
            continue

        # Derive a name by stripping the CAS number and concentration text
        # out of the line; whatever's left is the best-effort name.
        name_text = stripped
        if raw_cas:
            name_text = name_text.replace(raw_cas, "")
        if percent_match:
            name_text = name_text.replace(percent_match.group(1), "")
        name_text = re.sub(r"\s{2,}", " ", name_text).strip(" \t-|:")

        if raw_cas:
            disclosure_type = "cas_disclosed"
        elif _TRADE_SECRET_MARKERS.search(stripped):
            disclosure_type = "trade_secret"
        else:
            disclosure_type = "no_cas_disclosed"

        components.append(
            Component(
                raw_name=name_text or stripped,
                raw_cas=raw_cas,
                concentration_range=concentration_range,
                disclosure_type=disclosure_type,
            )
        )

    return components
