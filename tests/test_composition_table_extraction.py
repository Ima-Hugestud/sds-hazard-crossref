"""
Regression tests for table-based composition extraction, built against a
synthetic PDF that reproduces the real-world layout quirks discovered
against an actual manufacturer SDS during development:
  - A bordered table with columns [Description, CAS Number, EINECS
    Number, %, Note].
  - The concentration cell has no "%" symbol (e.g. "80 - 100"), relying
    entirely on the column header to signal what it is.
  - A stray section-header row ("4  First-aid measures") that PyMuPDF's
    table finder sometimes merges into the same detected table region,
    which must be filtered out rather than treated as a component.

The actual third-party PDF that surfaced this isn't checked into the repo
(no real manufacturer document is embedded here) — this fixture
reconstructs the same structural quirks synthetically instead.
"""

from pathlib import Path

import fitz  # PyMuPDF

from sds_hazard_crossref.parser_core.composition import (
    extract_components_for_sds,
    find_composition_table,
)
from sds_hazard_crossref.parser_core.sds_document import extract_sds


def _build_bordered_table_pdf(path: Path, include_bleed_through_row: bool = True) -> None:
    doc = fitz.open()
    page = doc.new_page()

    page.insert_text((50, 50), "3\nComposition/information on ingredients", fontsize=10)

    headers = ["Description", "CAS Number", "EINECS Number", "%", "Note"]
    row = ["POLYETHER DIAMINE", "9046-10-0", "", "80 - 100", ""]

    col_x = [50, 220, 340, 440, 490, 560]
    row_y = [100, 130, 160]
    if include_bleed_through_row:
        row_y.append(190)

    shape = page.new_shape()
    for x in col_x:
        shape.draw_line((x, row_y[0]), (x, row_y[-1]))
    for y in row_y:
        shape.draw_line((col_x[0], y), (col_x[-1], y))
    shape.finish()
    shape.commit()

    for i, h in enumerate(headers):
        page.insert_text((col_x[i] + 3, row_y[0] + 20), h, fontsize=8)
    for i, v in enumerate(row):
        page.insert_text((col_x[i] + 3, row_y[1] + 20), v, fontsize=8)
    if include_bleed_through_row:
        page.insert_text((col_x[0] + 3, row_y[2] + 20), "4", fontsize=8)
        page.insert_text((col_x[1] + 3, row_y[2] + 20), "First-aid measures", fontsize=8)

    doc.save(str(path))
    doc.close()


def _build_no_table_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 50),
        "SECTION 3: COMPOSITION/INFORMATION ON INGREDIENTS\n"
        "Chemical Name          CAS Number      Concentration\n"
        "Acetone                 67-64-1         95-100%\n",
        fontsize=9,
    )
    doc.save(str(path))
    doc.close()


def test_find_composition_table_detects_real_table_geometry(tmp_path):
    pdf_path = tmp_path / "bordered.pdf"
    _build_bordered_table_pdf(pdf_path)

    doc = fitz.open(str(pdf_path))
    data_rows, role_idx = find_composition_table(doc)
    doc.close()

    assert role_idx == {"name": 0, "cas": 1, "percent": 3}
    assert any("POLYETHER DIAMINE" in (row[0] or "") for row in data_rows)


def test_extract_components_for_sds_uses_table_when_available(tmp_path):
    pdf_path = tmp_path / "bordered.pdf"
    _build_bordered_table_pdf(pdf_path)

    sds = extract_sds(pdf_path)
    assert sds.composition_table_rows is not None

    components = extract_components_for_sds(sds)
    assert len(components) == 1
    c = components[0]
    assert c.raw_name == "POLYETHER DIAMINE"
    assert c.raw_cas == "9046-10-0"
    # No "%" symbol in the source cell — concentration still captured
    # because the column header identified it, not a text pattern match.
    assert c.concentration_range == "80 - 100"
    assert c.disclosure_type == "cas_disclosed"


def test_bleed_through_section_header_row_is_filtered_out(tmp_path):
    pdf_path = tmp_path / "bordered_with_bleed.pdf"
    _build_bordered_table_pdf(pdf_path, include_bleed_through_row=True)

    sds = extract_sds(pdf_path)
    components = extract_components_for_sds(sds)

    # Only the real data row should survive — the stray "4 / First-aid
    # measures" row has no CAS and no concentration, so it's filtered.
    assert len(components) == 1
    assert components[0].raw_name == "POLYETHER DIAMINE"


def test_falls_back_to_text_strategy_when_no_table_found(tmp_path):
    pdf_path = tmp_path / "no_table.pdf"
    _build_no_table_pdf(pdf_path)

    sds = extract_sds(pdf_path)
    assert sds.composition_table_rows is None

    components = extract_components_for_sds(sds)
    assert len(components) == 1
    assert components[0].raw_cas == "67-64-1"
