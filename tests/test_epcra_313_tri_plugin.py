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


def test_category_only_entry_does_not_crash_load_and_is_not_matchable(plugin):
    # "Xylene (mixed isomers)" has no CAS in the fixture — should be
    # counted, not silently dropped or matchable via a fabricated CAS.
    assert plugin._category_only_count == 1
    hit = plugin.lookup(None, "Xylene (mixed isomers)")
    assert hit.listed is False
