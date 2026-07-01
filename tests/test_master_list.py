from sds_hazard_crossref.parser_core.composition import Component
from sds_hazard_crossref.matching.engine import ResolvedComponent
from sds_hazard_crossref.plugins.base import ListHit
from sds_hazard_crossref.persistence.master_list import (
    ProductRef,
    upsert_component,
    load_master_list,
    save_master_list,
)


def _water_resolved():
    return ResolvedComponent(
        component=Component("Water", "7732-18-5", "0-5%", "cas_disclosed"),
        match_key_type="cas",
        cas="7732-18-5",
    )


def _product(sds_file="hardener_a.pdf", product_name="Example Hardener A"):
    return ProductRef(
        product_name=product_name,
        manufacturer="Example Chemical Co.",
        sds_file=sds_file,
        concentration_range="0-5%",
        date_processed="2026-07-01",
    )


def _hits():
    return {
        "niosh_rel": ListHit(
            list_id="niosh_rel", listed=False, match_method="cas",
            source_citation="NIOSH Pocket Guide", data_as_of="2026-01-01",
        )
    }


def test_upsert_creates_new_entry():
    master = {}
    upsert_component(master, "7732-18-5", _water_resolved(), _product(), _hits())
    entry = master["7732-18-5"]
    assert entry["primary_name"] == "Water"
    assert entry["cas"] == "7732-18-5"
    assert len(entry["products"]) == 1
    assert entry["list_hits"]["niosh_rel"]["listed"] is False
    assert entry["disposition"]["status"] == "unreviewed"


def test_upsert_adds_second_product_without_duplicating():
    master = {}
    upsert_component(master, "7732-18-5", _water_resolved(), _product("a.pdf", "Product A"), _hits())
    upsert_component(master, "7732-18-5", _water_resolved(), _product("b.pdf", "Product B"), _hits())
    assert len(master["7732-18-5"]["products"]) == 2


def test_upsert_same_product_reprocessed_updates_in_place():
    master = {}
    upsert_component(master, "7732-18-5", _water_resolved(), _product(), _hits())
    updated_product = _product()
    updated_product.date_processed = "2026-08-01"
    upsert_component(master, "7732-18-5", _water_resolved(), updated_product, _hits())
    assert len(master["7732-18-5"]["products"]) == 1
    assert master["7732-18-5"]["products"][0]["date_processed"] == "2026-08-01"


def test_upsert_name_variant_recorded_as_synonym_not_overwritten_primary():
    master = {}
    upsert_component(master, "7732-18-5", _water_resolved(), _product(), _hits())

    variant = ResolvedComponent(
        component=Component("Aqua", "7732-18-5", "0-5%", "cas_disclosed"),
        match_key_type="cas",
        cas="7732-18-5",
    )
    upsert_component(master, "7732-18-5", variant, _product("c.pdf", "Product C"), _hits())

    entry = master["7732-18-5"]
    assert entry["primary_name"] == "Water"  # unchanged, first-seen wins
    assert "Aqua" in entry["synonyms"]


def test_save_and_load_roundtrip(tmp_path):
    master = {}
    upsert_component(master, "7732-18-5", _water_resolved(), _product(), _hits())
    path = tmp_path / "components_master.json"

    save_master_list(path, master)
    reloaded = load_master_list(path)

    assert reloaded == master


def test_load_master_list_missing_file_returns_empty_dict(tmp_path):
    assert load_master_list(tmp_path / "does_not_exist.json") == {}
