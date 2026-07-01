from sds_hazard_crossref.parser_core.cas import (
    extract_cas_numbers,
    normalize_cas,
    is_valid_cas_checksum,
)


def test_extract_cas_numbers_finds_and_dedupes():
    text = "Contains acetone (CAS 67-64-1) and water 7732-18-5. Also 67-64-1 again."
    result = extract_cas_numbers(text)
    assert result == ["67-64-1", "7732-18-5"]


def test_extract_cas_numbers_empty_when_none_present():
    assert extract_cas_numbers("No chemical identifiers in this text.") == []


def test_normalize_cas_converts_stray_dash_variants():
    # en-dash and minus-sign variants sometimes appear from copy/paste or OCR
    assert normalize_cas("67\u201364\u20131") == "67-64-1"
    assert normalize_cas("  67-64-1  ") == "67-64-1"


def test_normalize_cas_rejects_non_cas_shape():
    assert normalize_cas("not a cas number") is None
    assert normalize_cas("12345") is None


def test_is_valid_cas_checksum_true_for_real_cas_numbers():
    # Water
    assert is_valid_cas_checksum("7732-18-5") is True
    # Acetone
    assert is_valid_cas_checksum("67-64-1") is True
    # Isopropanol
    assert is_valid_cas_checksum("67-63-0") is True


def test_is_valid_cas_checksum_false_for_bad_check_digit():
    assert is_valid_cas_checksum("7732-18-9") is False


def test_is_valid_cas_checksum_false_for_malformed_input():
    assert is_valid_cas_checksum("not-a-cas") is False
    assert is_valid_cas_checksum("7732-18") is False
