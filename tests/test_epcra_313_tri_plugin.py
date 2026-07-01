from pathlib import Path

import pytest

from sds_hazard_crossref.plugins.epcra_313_tri import EPCRATriPlugin

FIXTURE = Path(__file__).parent / "fixtures" / "epcra_313_tri_TEST_FIXTURE.csv"


@pytest.fixture
def plugin():
    p = EPCRATriPlugin(data_path=FIXTURE, data_as_of="TEST_FIXTURE-not-real-data")
    p.load()
    return p


def test_load_requires_existing_file():
    p = EPCRATriPlugin(data_path=Path("/does/not/exist.csv"), data_as_of="n/a")
    with pytest.raises(FileNotFoundError):
        p.load()


def test_lookup_before_load_raises():
    p = EPCRATriPlugin(data_path=FIXTURE, data_as_of="n/a")
    with pytest.raises(RuntimeError):
        p.lookup("108-88-3", "Toluene")


def test_cas_match_is_listed(plugin):
    hit = plugin.lookup("108-88-3", "Toluene")
    assert hit.listed is True
    assert hit.match_method == "cas"
    assert hit.list_id == "epcra_313_tri"
    assert hit.details["tri_listed_name"] == "Toluene"


def test_cas_not_in_list_is_not_listed(plugin):
    # Water is not TRI-listed
    hit = plugin.lookup("7732-18-5", "Water")
    assert hit.listed is False
    assert hit.match_method == "cas"


def test_name_only_match_when_no_cas(plugin):
    hit = plugin.lookup(None, "Benzene")
    assert hit.listed is True
    assert hit.match_method == "name"
    assert "no CAS" in hit.note.lower() or "name only" in hit.note.lower()


def test_no_cas_no_name_match_is_not_listed(plugin):
    hit = plugin.lookup(None, "Some Unrelated Fragrance")
    assert hit.listed is False
    assert hit.match_method == "name"


def test_data_as_of_is_reported():
    p = EPCRATriPlugin(data_path=FIXTURE, data_as_of="2026-07-01")
    assert p.data_as_of() == "2026-07-01"


def test_true_blank_category_entry_matches_by_name_with_no_code_shown(plugin):
    # "Xylene (mixed isomers)" has a truly blank CAS field in the fixture
    # (the defensive path — no category code available at all).
    hit = plugin.lookup(None, "Xylene (mixed isomers)")
    assert hit.listed is True
    assert hit.match_method == "category_name"
    assert hit.details["tri_category_code"] is None
    assert "not provided in source data" in hit.note


def test_category_code_entry_matches_by_exact_name(plugin):
    hit = plugin.lookup(None, "Antimony compounds")
    assert hit.listed is True
    assert hit.match_method == "category_name"
    assert hit.details["tri_category_code"] == "N010"
    assert hit.details["tri_listed_name"] == "Antimony compounds"
    assert "category" in hit.note.lower()


def test_category_code_entry_does_not_match_a_specific_compound_in_that_category(plugin):
    # "Antimony trioxide" is a specific compound, not literally named
    # "Antimony compounds" — must not fuzzy-match the category.
    hit = plugin.lookup(None, "Antimony trioxide")
    assert hit.listed is False


def test_category_only_count_reflects_both_blank_and_coded_entries(plugin):
    # 1 true-blank (Xylene mixed isomers) + 1 category-code (Antimony
    # compounds) in the fixture
    assert plugin._category_only_count == 2


def test_cas_match_still_takes_priority_over_category_lookup(plugin):
    # Sanity check: a real CAS match short-circuits before name/category
    # lookup is even attempted.
    hit = plugin.lookup("108-88-3", "Antimony compounds")  # deliberately mismatched name
    assert hit.match_method == "cas"
    assert hit.details["tri_listed_name"] == "Toluene"
