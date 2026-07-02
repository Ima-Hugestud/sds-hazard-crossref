"""
composition.py
Extracts structured component rows (name, CAS, concentration) from an
SDS's Section 3 (Composition/Information on Ingredients).

Two extraction strategies, tried in order:

1. **Table-based** (`extract_components_from_pdf`) — uses PyMuPDF's real
   table-geometry detection (`page.find_tables()`) to find the actual
   Section 3 table and read its columns directly. This is the strategy
   that should be used whenever a PDF is available, since it correctly
   handles table layouts that defeat text-based parsing: e.g. a real
   manufacturer SDS encountered during development split each cell of a
   3-column row onto its own line when flattened to text (name, CAS, and
   concentration on three separate lines, in that PDF's underlying
   content-stream order) — reading actual table cells sidesteps that
   entirely, since the table geometry tells us which cell belongs to
   which column regardless of what order the content stream emits them
   in. It also correctly handles concentration values with no "%" sign
   (relying on the column header, "%", rather than requiring the symbol
   to appear in the cell itself).

2. **Text-based fallback** (`extract_components_from_text`) — the
   original line-based heuristic, used when no PDF/table is available
   (e.g. plain-text SDS input) or no table matching a composition-table
   header signature was found on any page. Still best-effort by
   necessity, for the reasons in its own docstring below.

`extract_components_for_sds` picks between the two automatically given an
`SDSDocument` (see `sds_document.py`) and is the entry point most callers
should use.
"""

import re
from dataclasses import dataclass

from .cas import extract_cas_numbers

_PERCENT_PATTERN = re.compile(
    r"(<\s*\d{1,3}(?:\.\d+)?\s*%|\d{1,3}(?:\.\d+)?\s*-\s*\d{1,3}(?:\.\d+)?\s*%|\d{1,3}(?:\.\d+)?\s*%)"
)

# Column-header keyword signatures used by the table-based strategy to
# both (a) confirm a detected table is actually the composition table,
# and (b) map its columns to roles.
_HEADER_NAME_KEYWORDS = re.compile(
    r"description|chemical\s*name|component|ingredient", re.IGNORECASE
)
_HEADER_CAS_KEYWORDS = re.compile(r"\bcas\b", re.IGNORECASE)
_HEADER_PERCENT_KEYWORDS = re.compile(r"%|concentration|\bconc\b", re.IGNORECASE)

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


def extract_components_from_text(composition_text: str) -> list[Component]:
    """
    Parse Section 3 text into a list of Component rows using line-based
    heuristics. Fallback strategy — see module docstring for when this is
    used vs. the table-based strategy.

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


# Backward-compatible alias — the original name, kept so existing callers
# and tests that import `extract_components` for the text-based strategy
# don't break. New code should prefer `extract_components_for_sds` (picks
# the right strategy automatically) or call this explicitly by its new
# name when text-only extraction is specifically what's needed.
extract_components = extract_components_from_text


def _map_header_roles(header_row: list) -> dict[str, int] | None:
    """
    Map column index -> role ("cas" | "name" | "percent") from a table's
    header row. Returns None if the row doesn't look like a composition
    table header (must have both a CAS-like and a name-like column) —
    used to distinguish the real Section 3 table from other tables that
    happen to appear elsewhere in the document (e.g. an exposure-limits
    table in Section 8 mentioning the same chemical names has no CAS
    column, and is correctly rejected by this check).
    """
    role_idx: dict[str, int] = {}
    for i, cell in enumerate(header_row):
        text = cell or ""
        if "cas" not in role_idx and _HEADER_CAS_KEYWORDS.search(text):
            role_idx["cas"] = i
        elif "name" not in role_idx and _HEADER_NAME_KEYWORDS.search(text):
            role_idx["name"] = i
        elif "percent" not in role_idx and _HEADER_PERCENT_KEYWORDS.search(text):
            role_idx["percent"] = i

    if "cas" in role_idx and "name" in role_idx:
        return role_idx
    return None


def find_composition_table(pdf) -> tuple[list[list], dict[str, int]] | tuple[None, None]:
    """
    Search every page of an open PyMuPDF document for a table matching the
    composition-table header signature (a CAS-like column plus a
    name-like column). Returns (data_rows, role_idx) for the first match,
    or (None, None) if no such table is found anywhere in the document.

    `pdf` is a `fitz.Document` (typed loosely here to avoid importing
    PyMuPDF into this module just for a type hint — sds_document.py,
    which already depends on PyMuPDF, is the only caller).
    """
    for page in pdf:
        try:
            found = page.find_tables()
        except Exception:
            # A malformed page shouldn't abort the whole document — fall
            # through to the next page, and ultimately to the text-based
            # strategy if no page yields a usable table.
            continue

        for table in found.tables:
            rows = table.extract()
            if not rows:
                continue
            role_idx = _map_header_roles(rows[0])
            if role_idx:
                return rows[1:], role_idx

    return None, None


def extract_components_from_table_rows(
    data_rows: list[list], role_idx: dict[str, int]
) -> list[Component]:
    """
    Convert table data rows (as returned by `find_composition_table`) into
    Component objects, given a column-role mapping.

    Unlike the text-based strategy, the concentration column doesn't need
    a "%" symbol to be recognized as a concentration value here — the
    column header already told us what it is, which is exactly the kind
    of real-world case (a manufacturer's SDS with a "%" column header but
    bare numbers like "80 - 100" in the cells) that defeats the text-based
    strategy's percent regex.
    """
    components: list[Component] = []
    name_i = role_idx.get("name")
    cas_i = role_idx.get("cas")
    percent_i = role_idx.get("percent")

    for row in data_rows:
        def cell(i: int | None) -> str:
            if i is None or i >= len(row):
                return ""
            return (row[i] or "").strip()

        name = cell(name_i)
        raw_cas_cell = cell(cas_i)
        percent_cell = cell(percent_i)

        cas_matches = extract_cas_numbers(raw_cas_cell) if raw_cas_cell else []
        raw_cas = cas_matches[0] if cas_matches else None

        percent_match = _PERCENT_PATTERN.search(percent_cell) if percent_cell else None
        if percent_match:
            concentration_range = percent_match.group(1)
        else:
            concentration_range = percent_cell or None

        # Same requirement as the text-based strategy: need at least a CAS
        # or a concentration figure to count as a real data row. This also
        # filters out section-header bleed-through rows that sometimes get
        # merged into a detected table's region by PyMuPDF's table finder
        # (e.g. a stray "4 / First-aid measures" row immediately following
        # the real data, observed against a real-world SDS).
        if not name or (not raw_cas and not concentration_range):
            continue

        row_text = " ".join(c for c in row if c)
        if raw_cas:
            disclosure_type = "cas_disclosed"
        elif _TRADE_SECRET_MARKERS.search(row_text):
            disclosure_type = "trade_secret"
        else:
            disclosure_type = "no_cas_disclosed"

        components.append(
            Component(
                raw_name=name,
                raw_cas=raw_cas,
                concentration_range=concentration_range,
                disclosure_type=disclosure_type,
            )
        )

    return components


def extract_components_for_sds(sds) -> list[Component]:
    """
    The entry point most callers should use: uses the table-based strategy
    when `sds` (an `SDSDocument` — see `sds_document.py`) has composition
    table data attached (extracted once, while the PDF was open, by
    `extract_sds()`), falling back to the text-based strategy against
    `sds.composition_text` otherwise or if no composition table was found.

    Deliberately does not keep a live PDF handle on `SDSDocument` — that
    would risk file-handle leaks when processing a batch directory of many
    SDS files. The table data needed here is extracted once, up front,
    and stored as plain data instead.
    """
    if sds.composition_table_rows is not None:
        components = extract_components_from_table_rows(
            sds.composition_table_rows, sds.composition_table_roles
        )
        if components:
            return components

    return extract_components_from_text(sds.composition_text)
