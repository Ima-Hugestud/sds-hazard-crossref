"""
sds_document.py
Extracts text from SDS PDFs using PyMuPDF and splits it into the 16
standard GHS SDS sections.

This is a generalization of prop65-sds-checker's `pdf_extractor.py`. The
section-splitting logic (GHS-keyword gating + monotonic section-number
gating, so page-footer dates and digit-leading chemical names can't
masquerade as section headers) is carried over unchanged, since it's
already list-agnostic. What's new here: this tool needs the full section
dict (not just a Prop-65-relevant subset), plus best-effort Section 1
metadata extraction (product name, manufacturer, revision date), since the
master component list tracks which *product* each component came from.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

from .composition import find_composition_table

# Every GHS SDS section, 1-16, with the leading keyword(s) used to confirm a
# candidate header actually names that section (see _parse_sections).
_GHS_TITLE_KEYWORDS = re.compile(
    r"identif|hazard|composition|ingredient|first|fire|accidental|release|"
    r"handling|storage|exposure|personal protection|physical|chemical propert|"
    r"stabilit|reactiv|toxicolog|ecolog|disposal|transport|regulator|other",
    re.IGNORECASE,
)

_SECTION_PATTERN = re.compile(
    r"(?:^|\n)[\s=*#-]*(?:SECTION\s+)?(\d{1,2})[\s.:\u2013\-]+([A-Z][^\n]{2,60})",
    re.IGNORECASE,
)

# Best-effort Section 1 field extraction. SDS authors phrase these dozens of
# ways; these patterns cover common GHS-template phrasings. Fields that
# don't match are left as None rather than guessed — see extract_sds().
_PRODUCT_NAME_PATTERNS = (
    re.compile(r"product\s+name\s*[:\-]\s*(.+)", re.IGNORECASE),
    re.compile(r"trade\s+name\s*[:\-]\s*(.+)", re.IGNORECASE),
)
_MANUFACTURER_PATTERNS = (
    re.compile(r"manufacturer\s*[:\-]\s*(.+)", re.IGNORECASE),
    re.compile(r"company\s+name\s*[:\-]\s*(.+)", re.IGNORECASE),
    re.compile(r"supplier\s*[:\-]\s*(.+)", re.IGNORECASE),
)
_REVISION_DATE_PATTERNS = (
    re.compile(r"revision\s+date\s*[:\-]\s*(.+)", re.IGNORECASE),
    re.compile(r"date\s+of\s+(?:issue|revision)\s*[:\-]\s*(.+)", re.IGNORECASE),
    re.compile(r"(?:sds|version)\s+date\s*[:\-]\s*(.+)", re.IGNORECASE),
)


def _first_match(patterns: tuple[re.Pattern, ...], text: str) -> str | None:
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            value = m.group(1).strip()
            # Reject over-captures (a whole paragraph swallowed by a greedy
            # line-end match) rather than returning obvious garbage.
            if value and len(value) <= 200:
                return value.splitlines()[0].strip()
    return None


@dataclass
class SDSDocument:
    filename: str
    full_text: str
    sections: dict[int, str] = field(default_factory=dict)
    page_count: int = 0
    extraction_error: str | None = None

    # Best-effort Section 1 metadata. None if not confidently found — never
    # guessed (per PROJECT_SPEC.md: no fabricated identifiers).
    product_name: str | None = None
    manufacturer: str | None = None
    revision_date: str | None = None

    # Composition table data, extracted directly from real PDF table
    # geometry while the file was open (see extract_sds()) — plain data,
    # not a live PDF handle, to avoid file-handle leaks in batch mode.
    # None if no table matching the composition-table header signature
    # was found on any page; parser_core.composition falls back to the
    # text-based strategy in that case.
    composition_table_rows: list | None = None
    composition_table_roles: dict | None = None

    def section(self, number: int) -> str | None:
        """Text of a single GHS section (1-16), or None if not found."""
        return self.sections.get(number)

    @property
    def composition_text(self) -> str:
        """Section 3 (Composition/Information on Ingredients), or full text
        as a fallback if section splitting failed for this document."""
        return self.sections.get(3, self.full_text)

    @property
    def regulatory_text(self) -> str:
        """Section 15 (Regulatory Information), or empty string if absent."""
        return self.sections.get(15, "")


def extract_sds(pdf_path: Path) -> SDSDocument:
    """
    Open an SDS PDF and extract text, sections, and best-effort Section 1
    metadata. On any extraction failure, returns an SDSDocument with
    `extraction_error` set rather than raising — callers (batch mode
    especially) need to keep processing the rest of a directory and flag
    the failure in the report instead of crashing the run.
    """
    pdf_path = Path(pdf_path)
    doc = SDSDocument(filename=pdf_path.name, full_text="")

    try:
        with fitz.open(str(pdf_path)) as pdf:
            doc.page_count = len(pdf)
            doc.full_text = "\n".join(page.get_text() for page in pdf)
            doc.composition_table_rows, doc.composition_table_roles = (
                find_composition_table(pdf)
            )
    except Exception as e:  # pragma: no cover - exact exception varies by
        # PDF corruption mode; any failure here means "flag for manual
        # review", not "crash the batch run" (see PROJECT_SPEC.md scope).
        doc.extraction_error = str(e)
        return doc

    doc.sections = _parse_sections(doc.full_text)

    section_1 = doc.sections.get(1, doc.full_text[:2000])
    doc.product_name = _first_match(_PRODUCT_NAME_PATTERNS, section_1)
    doc.manufacturer = _first_match(_MANUFACTURER_PATTERNS, section_1)
    doc.revision_date = _first_match(_REVISION_DATE_PATTERNS, section_1)

    return doc


def _parse_sections(text: str) -> dict[int, str]:
    """
    Split SDS text into numbered GHS sections. Returns {section_number:
    section_text}.

    Two independent gates prevent stray lines from masquerading as section
    headers: (1) the header's title text must contain a real GHS section
    keyword, and (2) section numbers must increase monotonically (sections
    1..16 appear once, in document order). Together these stop a
    page-footer date ("8 December, 2025" -> bogus "Section 8") or a
    digit-leading chemical name ("1-Chloro-..." -> bogus "Section 1") from
    carving up a section.
    """
    candidates = [
        m for m in _SECTION_PATTERN.finditer(text)
        if _GHS_TITLE_KEYWORDS.search(m.group(2))
    ]

    accepted: list[tuple[int, int]] = []
    last_num = 0
    for m in candidates:
        sec_num = int(m.group(1))
        if 1 <= sec_num <= 16 and sec_num > last_num:
            accepted.append((sec_num, m.start()))
            last_num = sec_num

    sections: dict[int, str] = {}
    for i, (sec_num, start) in enumerate(accepted):
        end = accepted[i + 1][1] if i + 1 < len(accepted) else len(text)
        sections[sec_num] = text[start:end].strip()
    return sections
