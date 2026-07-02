"""
End-to-end integration test proving the full pipeline works together:
parse an SDS PDF -> extract components -> resolve each one -> check
against a real plugin -> persist into the master list.

This is the first test that exercises every layer built so far in one
pass, rather than each module in isolation.
"""

from pathlib import Path

import fitz  # PyMuPDF

from sds_hazard_crossref.parser_core.sds_document import extract_sds
from sds_hazard_crossref.parser_core.composition import extract_components_for_sds
from sds_hazard_crossref.matching.engine import resolve_component, check_against_lists
from sds_hazard_crossref.matching.synonyms import load_default_synonym_table
from sds_hazard_crossref.persistence.component_key import component_key
from sds_hazard_crossref.persistence.master_list import ProductRef, upsert_component
from sds_hazard_crossref.plugins.epcra_313_tri import EPCRATriPlugin

FIXTURE_TRI_CSV = Path(__file__).parent / "fixtures" / "epcra_313_tri_TEST_FIXTURE.csv"

# A synthetic (non-manufacturer) SDS: toluene is in the TRI test fixture,
# water is not — gives one hit and one miss to check in the same run.
SDS_TEXT = (
    "SECTION 1: IDENTIFICATION\n"
    "Product Name: Generic Solvent Blend\n"
    "Manufacturer: Example Chemical Supply Co.\n"
    "Revision Date: 2026-01-15\n"
    "SECTION 3: COMPOSITION/INFORMATION ON INGREDIENTS\n"
    "Chemical Name          CAS Number      Concentration\n"
    "Toluene                 108-88-3        50-60%\n"
    "Water                   7732-18-5       0-5%\n"
    "SECTION 15: REGULATORY INFORMATION\n"
    "See attached SDS for full regulatory disclosures.\n"
)


def test_full_pipeline_from_pdf_to_master_list(tmp_path):
    pdf_path = tmp_path / "solvent_blend_sds.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((36, 36), SDS_TEXT, fontsize=9)
    doc.save(str(pdf_path))
    doc.close()

    sds = extract_sds(pdf_path)
    assert sds.extraction_error is None

    components = extract_components_for_sds(sds)
    assert len(components) == 2

    synonym_table = load_default_synonym_table()
    plugin = EPCRATriPlugin(data_path=FIXTURE_TRI_CSV, data_as_of="TEST_FIXTURE")
    plugin.load()

    master = {}
    for row_index, component in enumerate(components):
        resolved = resolve_component(component, synonym_table)
        hits = check_against_lists(resolved, [plugin])
        key = component_key(resolved, sds.filename, row_index)
        product = ProductRef(
            product_name=sds.product_name,
            manufacturer=sds.manufacturer,
            sds_file=sds.filename,
            concentration_range=component.concentration_range,
            date_processed="2026-07-01",
        )
        upsert_component(master, key, resolved, product, hits)

    assert set(master.keys()) == {"108-88-3", "7732-18-5"}

    toluene = master["108-88-3"]
    assert toluene["primary_name"] == "Toluene"
    assert toluene["list_hits"]["epcra_313_tri"]["listed"] is True
    assert toluene["products"][0]["product_name"] == "Generic Solvent Blend"
    assert toluene["products"][0]["manufacturer"] == "Example Chemical Supply Co."

    water = master["7732-18-5"]
    assert water["list_hits"]["epcra_313_tri"]["listed"] is False
