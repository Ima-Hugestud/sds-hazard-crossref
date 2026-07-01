from unittest.mock import patch

from sds_hazard_crossref.refresh_cli import main
from sds_hazard_crossref.refresh.epcra_313_tri_fetch import FetchResult, TriFetchError


@patch("sds_hazard_crossref.refresh_cli.fetch_epcra_313_tri")
def test_successful_refresh_prints_summary_and_returns_zero(mock_fetch, tmp_path, capsys):
    output = tmp_path / "tri.csv"
    mock_fetch.return_value = FetchResult(
        rows_written=810,
        category_only_rows=34,
        output_path=output,
        raw_cache_path=tmp_path / "tri.raw.json",
    )

    exit_code = main(["--list", "epcra-313-tri", "--output", str(output)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "810 rows" in out
    assert "34" in out
    assert "category-level" in out


@patch("sds_hazard_crossref.refresh_cli.fetch_epcra_313_tri")
def test_fetch_error_returns_one_and_prints_to_stderr(mock_fetch, tmp_path, capsys):
    mock_fetch.side_effect = TriFetchError("could not identify columns")

    exit_code = main(["--list", "epcra-313-tri", "--output", str(tmp_path / "tri.csv")])

    assert exit_code == 1
    assert "could not identify columns" in capsys.readouterr().err


def test_unknown_list_choice_rejected_by_argparse(tmp_path):
    # argparse itself should reject an unregistered --list value before
    # main()'s body even runs
    import pytest
    with pytest.raises(SystemExit):
        main(["--list", "not-a-real-list", "--output", str(tmp_path / "out.csv")])
