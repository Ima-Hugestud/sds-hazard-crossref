from pathlib import Path

import fitz  # PyMuPDF
import pytest

from sds_hazard_crossref.parser_core.sds_document import (
    _parse_sections,
    extract_sds,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def synthetic_sds_text() -> str:
    return (FIXTURES / "synthetic_acetone_sds.txt").read_text(encoding="utf-8")


def test_parse_sections_splits_expected_sections(synthetic_sds_text):
    sections = _parse_sections(synthetic_sds_text)
    assert set(sections) == {1, 2, 3, 4, 8, 11, 15}
    assert "Acetone" in sections[3]
    assert "67-64-1" in sections[3]
    assert "Proposition 65" in sections[15]


def test_parse_sections_does_not_treat_footer_date_as_a_section():
    # A page-footer-style date line should not be mistaken for a section
    # header just because it starts with a digit followed by punctuation.
    text = (
        "SECTION 1: IDENTIFICATION\nProduct Name: Test\n"
        "8 December, 2025\n"
        "SECTION 3: COMPOSITION/INFORMATION ON INGREDIENTS\nSome text.\n"
    )
    sections = _parse_sections(text)
    assert set(sections) == {1, 3}


def test_parse_sections_does_not_treat_digit_leading_chemical_name_as_a_section():
    text = (
        "SECTION 3: COMPOSITION/INFORMATION ON INGREDIENTS\n"
        "1-Chloro-4-trifluoromethylbenzene, CAS 121-43-7\n"
        "SECTION 4: FIRST AID MEASURES\nRinse with water.\n"
    )
    sections = _parse_sections(text)
    assert set(sections) == {3, 4}


def test_extract_sds_end_to_end(tmp_path, synthetic_sds_text):
    pdf_path = tmp_path / "synthetic_acetone_sds.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((36, 36), synthetic_sds_text, fontsize=9)
    doc.save(str(pdf_path))
    doc.close()

    result = extract_sds(pdf_path)

    assert result.extraction_error is None
    assert result.page_count == 1
    assert "67-64-1" in result.composition_text
    assert "Proposition 65" in result.regulatory_text
    # Best-effort Section 1 metadata
    assert result.product_name == "Generic Acetone, Technical Grade"
    assert result.manufacturer == "Example Chemical Supply Co."
    assert result.revision_date == "2026-01-15"


def test_extract_sds_missing_file_flags_error_not_crash(tmp_path):
    missing = tmp_path / "does_not_exist.pdf"
    result = extract_sds(missing)
    assert result.extraction_error is not None
    assert result.full_text == ""
