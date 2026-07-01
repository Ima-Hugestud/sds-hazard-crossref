from sds_hazard_crossref.parser_core.composition import Component
from sds_hazard_crossref.matching.engine import ResolvedComponent
from sds_hazard_crossref.persistence.component_key import component_key


def test_cas_match_key_is_the_cas_number():
    resolved = ResolvedComponent(
        component=Component("Water", "7732-18-5", "0-5%", "cas_disclosed"),
        match_key_type="cas",
        cas="7732-18-5",
    )
    assert component_key(resolved, "example_sds.pdf", 0) == "7732-18-5"


def test_name_match_key_is_prefixed_to_avoid_collision_with_cas_keys():
    resolved = ResolvedComponent(
        component=Component("Fragrance Blend XJ-9", None, "1-5%", "no_cas_disclosed"),
        match_key_type="name",
        normalized_name="fragrance blend xj-9",
    )
    assert component_key(resolved, "example_sds.pdf", 2) == "name::fragrance blend xj-9"


def test_unresolvable_key_is_scoped_per_sds_and_row_never_merged_by_name():
    a = ResolvedComponent(
        component=Component("Proprietary amine blend", None, "10-30%", "trade_secret"),
        match_key_type="unresolvable",
    )
    key_a = component_key(a, "manufacturer_a_sds.pdf", 3)
    key_b = component_key(a, "manufacturer_b_sds.pdf", 3)
    # Same generic placeholder name, different SDS -> must NOT collide
    assert key_a != key_b
    assert key_a == "unresolved::manufacturer_a_sds.pdf::3"


def test_unresolvable_key_stable_for_same_sds_and_row_across_reruns():
    resolved = ResolvedComponent(
        component=Component("Proprietary blend", None, "10-30%", "trade_secret"),
        match_key_type="unresolvable",
    )
    key_1 = component_key(resolved, "example_sds.pdf", 1)
    key_2 = component_key(resolved, "example_sds.pdf", 1)
    assert key_1 == key_2
