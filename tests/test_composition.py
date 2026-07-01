from sds_hazard_crossref.parser_core.composition import extract_components


def test_extracts_cas_disclosed_rows():
    text = (
        "SECTION 3: COMPOSITION/INFORMATION ON INGREDIENTS\n"
        "Chemical Name          CAS Number      Concentration\n"
        "Acetone                 67-64-1         95-100%\n"
        "Water                   7732-18-5       0-5%\n"
    )
    components = extract_components(text)
    assert len(components) == 2

    assert components[0].raw_cas == "67-64-1"
    assert "Acetone" in components[0].raw_name
    assert components[0].concentration_range == "95-100%"
    assert components[0].disclosure_type == "cas_disclosed"

    assert components[1].raw_cas == "7732-18-5"
    assert components[1].concentration_range == "0-5%"


def test_flags_trade_secret_entry_with_no_cas():
    text = (
        "SECTION 3: COMPOSITION/INFORMATION ON INGREDIENTS\n"
        "Proprietary amine blend                10-30%\n"
    )
    components = extract_components(text)
    assert len(components) == 1
    assert components[0].raw_cas is None
    assert components[0].disclosure_type == "trade_secret"


def test_no_cas_no_trade_secret_marker_is_no_cas_disclosed():
    text = (
        "SECTION 3: COMPOSITION/INFORMATION ON INGREDIENTS\n"
        "Fragrance blend                1-5%\n"
    )
    components = extract_components(text)
    assert len(components) == 1
    assert components[0].disclosure_type == "no_cas_disclosed"


def test_skips_header_and_blank_lines():
    text = (
        "SECTION 3: COMPOSITION/INFORMATION ON INGREDIENTS\n"
        "\n"
        "Chemical Name    CAS Number    Concentration\n"
        "Toluene          108-88-3      50-60%\n"
    )
    components = extract_components(text)
    assert len(components) == 1
    assert components[0].raw_cas == "108-88-3"


def test_skips_prose_lines_with_no_cas_or_percentage():
    text = (
        "SECTION 3: COMPOSITION/INFORMATION ON INGREDIENTS\n"
        "See Section 8 for exposure controls.\n"
        "Toluene          108-88-3      50-60%\n"
    )
    components = extract_components(text)
    assert len(components) == 1
