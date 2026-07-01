import pytest

from sds_hazard_crossref.parser_core.composition import Component
from sds_hazard_crossref.matching.engine import resolve_component, check_against_lists
from sds_hazard_crossref.matching.synonyms import load_default_synonym_table
from sds_hazard_crossref.plugins.base import HazardListPlugin, ListHit


@pytest.fixture
def synonym_table():
    return load_default_synonym_table()


class FakePlugin(HazardListPlugin):
    """Minimal test double: 'lists' water as a hit, everything else a miss."""

    list_id = "fake_list"
    display_name = "Fake Test List"

    def load(self) -> None:
        self.loaded = True

    def lookup(self, cas, name) -> ListHit:
        listed = cas == "7732-18-5"
        return ListHit(
            list_id=self.list_id,
            listed=listed,
            match_method="cas" if cas else "name",
            source_citation=self.display_name,
            data_as_of="2026-07-01",
        )

    def data_as_of(self) -> str:
        return "2026-07-01"


def test_resolve_component_valid_cas_is_primary_key(synonym_table):
    component = Component(
        raw_name="Water", raw_cas="7732-18-5", concentration_range="0-5%",
        disclosure_type="cas_disclosed",
    )
    resolved = resolve_component(component, synonym_table)
    assert resolved.match_key_type == "cas"
    assert resolved.cas == "7732-18-5"


def test_resolve_component_invalid_checksum_falls_back_to_name(synonym_table):
    component = Component(
        raw_name="Water", raw_cas="7732-18-9", concentration_range="0-5%",
        disclosure_type="cas_disclosed",
    )
    resolved = resolve_component(component, synonym_table)
    # "Water" is in the synonym table, so name resolution finds the real CAS
    assert resolved.match_key_type == "cas"
    assert resolved.cas == "7732-18-5"
    assert "invalid check digit" in resolved.note


def test_resolve_component_trade_secret_is_unresolvable(synonym_table):
    component = Component(
        raw_name="Proprietary amine blend", raw_cas=None,
        concentration_range="10-30%", disclosure_type="trade_secret",
    )
    resolved = resolve_component(component, synonym_table)
    assert resolved.match_key_type == "unresolvable"
    assert "manual follow-up" in resolved.note.lower()
    assert resolved.cas is None


def test_resolve_component_name_only_uses_synonym_table(synonym_table):
    component = Component(
        raw_name="MEK", raw_cas=None, concentration_range="10-20%",
        disclosure_type="no_cas_disclosed",
    )
    resolved = resolve_component(component, synonym_table)
    assert resolved.match_key_type == "cas"
    assert resolved.cas == "78-93-3"


def test_resolve_component_name_only_no_synonym_falls_back_to_name(synonym_table):
    component = Component(
        raw_name="Fragrance Blend XJ-9", raw_cas=None,
        concentration_range="1-5%", disclosure_type="no_cas_disclosed",
    )
    resolved = resolve_component(component, synonym_table)
    assert resolved.match_key_type == "name"
    assert resolved.normalized_name == "fragrance blend xj-9"
    assert resolved.cas is None


def test_resolve_component_no_name_no_cas_is_unresolvable(synonym_table):
    component = Component(
        raw_name="", raw_cas=None, concentration_range="1-5%",
        disclosure_type="no_cas_disclosed",
    )
    resolved = resolve_component(component, synonym_table)
    assert resolved.match_key_type == "unresolvable"


def test_check_against_lists_dispatches_cas_match(synonym_table):
    component = Component(
        raw_name="Water", raw_cas="7732-18-5", concentration_range="0-5%",
        disclosure_type="cas_disclosed",
    )
    resolved = resolve_component(component, synonym_table)
    hits = check_against_lists(resolved, [FakePlugin()])
    assert hits["fake_list"].listed is True


def test_check_against_lists_unresolvable_never_calls_lookup(synonym_table):
    component = Component(
        raw_name="Proprietary blend", raw_cas=None,
        concentration_range="10-30%", disclosure_type="trade_secret",
    )
    resolved = resolve_component(component, synonym_table)
    hits = check_against_lists(resolved, [FakePlugin()])
    assert hits["fake_list"].match_method == "unresolvable"
    assert hits["fake_list"].listed is False
    assert "manual follow-up" in hits["fake_list"].note.lower()
