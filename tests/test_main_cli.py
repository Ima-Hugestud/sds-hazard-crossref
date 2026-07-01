import json
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from sds_hazard_crossref.main import main
from sds_hazard_crossref.persistence.dispositions import (
    record_list_disposition,
    save_dispositions,
)

FIXTURE_TRI_CSV = Path(__file__).parent / "fixtures" / "epcra_313_tri_TEST_FIXTURE.csv"

SDS_TEXT_TOLUENE = (
    "SECTION 1: IDENTIFICATION\n"
    "Product Name: Generic Solvent Blend\n"
    "Manufacturer: Example Chemical Supply Co.\n"
    "Revision Date: 2026-01-15\n"
    "SECTION 3: COMPOSITION/INFORMATION ON INGREDIENTS\n"
    "Chemical Name          CAS Number      Concentration\n"
    "Toluene                 108-88-3        50-60%\n"
    "Water                   7732-18-5       0-5%\n"
)

SDS_TEXT_METHANOL = (
    "SECTION 1: IDENTIFICATION\n"
    "Product Name: Generic Cleaner\n"
    "Manufacturer: Example Chemical Supply Co.\n"
    "Revision Date: 2026-02-01\n"
    "SECTION 3: COMPOSITION/INFORMATION ON INGREDIENTS\n"
    "Chemical Name          CAS Number      Concentration\n"
    "Methanol                67-56-1         10-20%\n"
)


def _write_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((36, 36), text, fontsize=9)
    doc.save(str(path))
    doc.close()


def test_single_file_mode_creates_master_list(tmp_path, capsys):
    pdf_path = tmp_path / "solvent.pdf"
    _write_pdf(pdf_path, SDS_TEXT_TOLUENE)
    master_path = tmp_path / "components_master.json"
    dispositions_path = tmp_path / "dispositions.json"

    exit_code = main([
        str(pdf_path),
        "--master-list", str(master_path),
        "--dispositions", str(dispositions_path),
        "--epcra-tri-data", str(FIXTURE_TRI_CSV),
        "--epcra-tri-data-as-of", "TEST_FIXTURE",
    ])

    assert exit_code == 0
    assert master_path.exists()
    master = json.loads(master_path.read_text())
    assert "108-88-3" in master
    assert master["108-88-3"]["list_hits"]["epcra_313_tri"]["listed"] is True

    captured = capsys.readouterr()
    assert "Toluene: listed on epcra_313_tri" in captured.out
    assert "does not replace" in captured.out


def test_batch_directory_mode_processes_all_pdfs(tmp_path):
    sds_dir = tmp_path / "sds_library"
    sds_dir.mkdir()
    _write_pdf(sds_dir / "solvent.pdf", SDS_TEXT_TOLUENE)
    _write_pdf(sds_dir / "cleaner.pdf", SDS_TEXT_METHANOL)
    master_path = tmp_path / "components_master.json"

    exit_code = main([
        str(sds_dir),
        "--master-list", str(master_path),
        "--dispositions", str(tmp_path / "dispositions.json"),
        "--epcra-tri-data", str(FIXTURE_TRI_CSV),
    ])

    assert exit_code == 0
    master = json.loads(master_path.read_text())
    # Toluene + water from the first SDS, methanol from the second
    assert "108-88-3" in master
    assert "7732-18-5" in master
    assert "67-56-1" in master


def test_missing_input_path_returns_error_exit_code(tmp_path, capsys):
    exit_code = main([str(tmp_path / "does_not_exist.pdf")])
    assert exit_code == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_empty_directory_returns_error_exit_code(tmp_path, capsys):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    exit_code = main([str(empty_dir)])
    assert exit_code == 1
    assert "no sds pdf files found" in capsys.readouterr().err.lower()


def test_missing_epcra_tri_data_file_returns_error_exit_code(tmp_path, capsys):
    pdf_path = tmp_path / "solvent.pdf"
    _write_pdf(pdf_path, SDS_TEXT_TOLUENE)

    exit_code = main([
        str(pdf_path),
        "--master-list", str(tmp_path / "components_master.json"),
        "--dispositions", str(tmp_path / "dispositions.json"),
        "--epcra-tri-data", str(tmp_path / "does_not_exist.csv"),
    ])

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_runs_without_any_plugin_data_but_warns(tmp_path, capsys):
    pdf_path = tmp_path / "solvent.pdf"
    _write_pdf(pdf_path, SDS_TEXT_TOLUENE)
    master_path = tmp_path / "components_master.json"

    exit_code = main([
        str(pdf_path),
        "--master-list", str(master_path),
        "--dispositions", str(tmp_path / "dispositions.json"),
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "no --epcra-tri-data supplied" in captured.err.lower()

    master = json.loads(master_path.read_text())
    assert "108-88-3" in master  # still parsed and persisted
    assert master["108-88-3"]["list_hits"] == {}  # but nothing was screened


def test_disposition_survives_a_cli_rerun(tmp_path):
    pdf_path = tmp_path / "solvent.pdf"
    _write_pdf(pdf_path, SDS_TEXT_TOLUENE)
    master_path = tmp_path / "components_master.json"
    dispositions_path = tmp_path / "dispositions.json"

    # First run establishes the list_hits
    main([
        str(pdf_path),
        "--master-list", str(master_path),
        "--dispositions", str(dispositions_path),
        "--epcra-tri-data", str(FIXTURE_TRI_CSV),
    ])

    # A reviewer records a disposition decision between runs
    dispositions = json.loads(dispositions_path.read_text())
    record_list_disposition(
        dispositions, "108-88-3", "epcra_313_tri",
        status="acknowledged", reviewer="J. Reviewer",
        notes="Confirmed, no facility-level action needed.",
        last_updated="2026-07-01",
    )
    save_dispositions(dispositions_path, dispositions)

    # Second run (e.g. re-processing the same SDS) must not lose it
    main([
        str(pdf_path),
        "--master-list", str(master_path),
        "--dispositions", str(dispositions_path),
        "--epcra-tri-data", str(FIXTURE_TRI_CSV),
    ])

    master = json.loads(master_path.read_text())
    hit = master["108-88-3"]["list_hits"]["epcra_313_tri"]
    assert hit["listed"] is True
    assert hit["disposition"]["status"] == "acknowledged"
