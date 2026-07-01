from sds_hazard_crossref.parser_core.names import normalize_name


def test_normalize_name_case_and_whitespace():
    assert normalize_name("  Methyl Ethyl   Ketone  ") == "methyl ethyl ketone"


def test_normalize_name_strips_edge_punctuation():
    assert normalize_name(".Acetone,") == "acetone"


def test_normalize_name_does_not_alter_salt_or_hydrate_notation():
    # Deliberate: stripping "sodium" or "hydrate" would conflate distinct
    # substances with different CAS numbers. See names.py module docstring.
    assert normalize_name("Sodium Chloride") == "sodium chloride"
    assert normalize_name("Copper Sulfate Pentahydrate") == "copper sulfate pentahydrate"


def test_normalize_name_empty_input():
    assert normalize_name("") == ""
