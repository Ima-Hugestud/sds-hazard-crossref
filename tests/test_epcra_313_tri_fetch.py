import json
from unittest.mock import patch

import pytest

from sds_hazard_crossref.refresh.epcra_313_tri_fetch import (
    TriFetchError,
    fetch_epcra_313_tri,
)


class _FakeResponse:
    """Minimal stand-in for the context-manager object urlopen() returns."""

    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return self._payload


def _json_response(rows: list[dict]) -> _FakeResponse:
    return _FakeResponse(json.dumps(rows).encode("utf-8"))


@patch("sds_hazard_crossref.refresh.epcra_313_tri_fetch.urllib.request.urlopen")
def test_successful_fetch_writes_csv(mock_urlopen, tmp_path):
    rows = [
        {"chem_name": "Toluene", "cas_number": "108-88-3"},
        {"chem_name": "Xylene (mixed isomers)", "cas_number": ""},
    ]
    # First page returns the rows (fewer than page size -> pagination stops)
    mock_urlopen.return_value = _json_response(rows)

    output_csv = tmp_path / "tri_data.csv"
    raw_cache = tmp_path / "tri_data.raw.json"
    result = fetch_epcra_313_tri(output_csv, raw_cache)

    assert result.rows_written == 2
    assert result.category_only_rows == 1
    assert output_csv.exists()

    content = output_csv.read_text()
    assert "Toluene,108-88-3" in content
    assert "Xylene (mixed isomers)," in content


@patch("sds_hazard_crossref.refresh.epcra_313_tri_fetch.urllib.request.urlopen")
def test_pagination_stops_on_short_batch(mock_urlopen, tmp_path):
    full_page = [{"chem_name": f"Chemical {i}", "cas_number": f"{1000+i}-00-0"} for i in range(500)]
    short_page = [{"chem_name": "Last Chemical", "cas_number": "9999-99-9"}]
    mock_urlopen.side_effect = [
        _json_response(full_page),
        _json_response(short_page),
    ]

    output_csv = tmp_path / "tri_data.csv"
    raw_cache = tmp_path / "tri_data.raw.json"
    result = fetch_epcra_313_tri(output_csv, raw_cache)

    assert result.rows_written == 501
    assert mock_urlopen.call_count == 2  # stopped after the short (final) page


@patch("sds_hazard_crossref.refresh.epcra_313_tri_fetch.urllib.request.urlopen")
def test_unrecognized_field_names_raises_with_actual_keys_shown(mock_urlopen, tmp_path):
    rows = [{"some_unexpected_field": "Toluene", "another_field": "108-88-3"}]
    mock_urlopen.return_value = _json_response(rows)

    output_csv = tmp_path / "tri_data.csv"
    raw_cache = tmp_path / "tri_data.raw.json"

    with pytest.raises(TriFetchError) as exc_info:
        fetch_epcra_313_tri(output_csv, raw_cache)

    assert "some_unexpected_field" in str(exc_info.value)
    # Raw response must still be cached even though CSV writing failed
    assert raw_cache.exists()
    assert not output_csv.exists()


@patch("sds_hazard_crossref.refresh.epcra_313_tri_fetch.urllib.request.urlopen")
def test_empty_response_raises(mock_urlopen, tmp_path):
    mock_urlopen.return_value = _json_response([])

    with pytest.raises(TriFetchError, match="no rows"):
        fetch_epcra_313_tri(tmp_path / "out.csv", tmp_path / "raw.json")


@patch("sds_hazard_crossref.refresh.epcra_313_tri_fetch.urllib.request.urlopen")
def test_network_error_raises_tri_fetch_error(mock_urlopen, tmp_path):
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("connection refused")

    with pytest.raises(TriFetchError, match="Failed to fetch"):
        fetch_epcra_313_tri(tmp_path / "out.csv", tmp_path / "raw.json")


@patch("sds_hazard_crossref.refresh.epcra_313_tri_fetch.urllib.request.urlopen")
def test_alternate_recognized_field_names_also_work(mock_urlopen, tmp_path):
    # Second candidate in each list, to confirm the fallback order works
    rows = [{"chemical_name": "Benzene", "cas_registry_number": "71-43-2"}]
    mock_urlopen.return_value = _json_response(rows)

    output_csv = tmp_path / "out.csv"
    result = fetch_epcra_313_tri(output_csv, tmp_path / "raw.json")

    assert result.rows_written == 1
    assert "Benzene,71-43-2" in output_csv.read_text()
