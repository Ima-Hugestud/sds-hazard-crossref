from sds_hazard_crossref.parser_core.composition import Component
from sds_hazard_crossref.matching.engine import ResolvedComponent
from sds_hazard_crossref.plugins.base import ListHit
from sds_hazard_crossref.persistence.master_list import ProductRef, upsert_component
from sds_hazard_crossref.persistence.dispositions import (
    record_component_disposition,
    record_list_disposition,
    apply_dispositions,
    load_dispositions,
    save_dispositions,
)


def _build_master_with_one_hit():
    master = {}
    resolved = ResolvedComponent(
        component=Component("Toluene", "108-88-3", "50-60%", "cas_disclosed"),
        match_key_type="cas",
        cas="108-88-3",
    )
    product = ProductRef(
        product_name="Example Solvent Blend", manufacturer="Example Chemical Co.",
        sds_file="solvent.pdf", concentration_range="50-60%", date_processed="2026-07-01",
    )
    hits = {
        "epcra_313_tri": ListHit(
            list_id="epcra_313_tri", listed=True, match_method="cas",
            source_citation="EPA TRI", data_as_of="2026-01-01",
        )
    }
    upsert_component(master, "108-88-3", resolved, product, hits)
    return master


def test_record_and_apply_list_disposition():
    master = _build_master_with_one_hit()
    dispositions = {}
    record_list_disposition(
        dispositions, "108-88-3", "epcra_313_tri",
        status="no_action_needed",
        reviewer="J. Reviewer",
        notes="Listed on TRI but below our facility's reportable threshold.",
        last_updated="2026-07-01",
    )
    apply_dispositions(master, dispositions)

    hit = master["108-88-3"]["list_hits"]["epcra_313_tri"]
    assert hit["disposition"]["status"] == "no_action_needed"
    assert "reportable threshold" in hit["disposition"]["notes"]
    # The underlying list determination itself is untouched by the disposition
    assert hit["listed"] is True


def test_record_and_apply_component_disposition():
    master = _build_master_with_one_hit()
    dispositions = {}
    record_component_disposition(
        dispositions, "108-88-3", status="reviewed",
        reviewer="J. Reviewer", notes="All hits reviewed.",
        last_updated="2026-07-01",
    )
    apply_dispositions(master, dispositions)
    assert master["108-88-3"]["disposition"]["status"] == "reviewed"


def test_disposition_survives_a_rerun_that_regenerates_list_hits():
    """
    Simulates the exact scenario the spec calls out: a fresh run
    regenerates list_hits (e.g. the source data was refreshed and now says
    listed=False), and the human's disposition from the prior run must
    still be layered back on, not lost.
    """
    master = _build_master_with_one_hit()
    dispositions = {}
    record_list_disposition(
        dispositions, "108-88-3", "epcra_313_tri", status="no_action_needed",
        reviewer="J. Reviewer", notes="Below threshold.", last_updated="2026-07-01",
    )
    apply_dispositions(master, dispositions)

    # Simulate a re-run: list_hits gets freshly overwritten (e.g. data updated)
    resolved = ResolvedComponent(
        component=Component("Toluene", "108-88-3", "50-60%", "cas_disclosed"),
        match_key_type="cas", cas="108-88-3",
    )
    product = ProductRef(
        product_name="Example Solvent Blend", manufacturer="Example Chemical Co.",
        sds_file="solvent.pdf", concentration_range="50-60%", date_processed="2026-08-01",
    )
    new_hits = {
        "epcra_313_tri": ListHit(
            list_id="epcra_313_tri", listed=False, match_method="cas",
            source_citation="EPA TRI", data_as_of="2026-08-01",
        )
    }
    upsert_component(master, "108-88-3", resolved, product, new_hits)
    # upsert_component alone does NOT carry the disposition forward —
    # apply_dispositions must be called again after every list_hits refresh
    apply_dispositions(master, dispositions)

    hit = master["108-88-3"]["list_hits"]["epcra_313_tri"]
    assert hit["listed"] is False  # fresh determination
    assert hit["disposition"]["status"] == "no_action_needed"  # prior review preserved


def test_dispositions_roundtrip(tmp_path):
    dispositions = {}
    record_list_disposition(
        dispositions, "108-88-3", "epcra_313_tri", status="no_action_needed",
        reviewer="J. Reviewer", notes="Below threshold.", last_updated="2026-07-01",
    )
    path = tmp_path / "dispositions.json"
    save_dispositions(path, dispositions)
    reloaded = load_dispositions(path)
    assert reloaded == dispositions


def test_apply_dispositions_ignores_components_with_no_recorded_disposition():
    master = _build_master_with_one_hit()
    apply_dispositions(master, {})
    # Untouched — default "unreviewed" from upsert_component stands
    assert master["108-88-3"]["disposition"]["status"] == "unreviewed"
    assert "disposition" not in master["108-88-3"]["list_hits"]["epcra_313_tri"]
