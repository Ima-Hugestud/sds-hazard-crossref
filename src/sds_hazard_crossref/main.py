"""
main.py
CLI entry point: `sds-crossref`.

Usage:
    sds-crossref path/to/one.pdf
    sds-crossref path/to/sds_library_directory/

Processes one SDS or a directory of SDS PDFs through the full pipeline
(parser_core -> matching engine -> hazard-list plugins -> persistence),
updating the master component list and disposition log in place.

Plugin data sources are never bundled or fabricated as defaults (see
PROJECT_SPEC.md and DATA_SOURCES_REFERENCE.md) — they must be supplied
explicitly via CLI flags. Phase 1 wires up EPCRA §313/TRI only; each
additional plugin gets its own flag as it's built (see plugins/ package).
If no plugin data is supplied, the tool still runs — components are
parsed and persisted to the master list, just with no hazard-list
screening performed, and a warning says so explicitly rather than the
run silently doing less than the user expects.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from .matching.engine import check_against_lists, resolve_component
from .matching.synonyms import load_default_synonym_table
from .parser_core.composition import extract_components_for_sds
from .parser_core.sds_document import extract_sds
from .persistence.component_key import component_key
from .persistence.dispositions import apply_dispositions, load_dispositions, save_dispositions
from .persistence.master_list import (
    ProductRef,
    load_master_list,
    save_master_list,
    upsert_component,
)
from .plugins.base import HazardListPlugin
from .plugins.epcra_313_tri import EPCRATriPlugin

DISCLAIMER = (
    "This tool assists hazard identification; it does not replace a qualified "
    "EHS/industrial hygiene professional's judgment."
)


def build_plugins(args: argparse.Namespace) -> list[HazardListPlugin]:
    """
    Load every plugin the user provided data for. Raises FileNotFoundError
    (with a clear, actionable message) if a supplied path doesn't exist —
    caught and reported by `main()`, never a bare traceback.
    """
    plugins: list[HazardListPlugin] = []

    if args.epcra_tri_data:
        plugin = EPCRATriPlugin(
            data_path=args.epcra_tri_data, data_as_of=args.epcra_tri_data_as_of
        )
        plugin.load()
        plugins.append(plugin)
    else:
        print(
            "Warning: no --epcra-tri-data supplied. EPCRA \u00a7313/TRI screening "
            "will be skipped for this run. See DATA_SOURCES_REFERENCE.md row 8 "
            "for how to obtain real TRI data.",
            file=sys.stderr,
        )

    return plugins


def discover_sds_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.glob("*.pdf"))
    raise FileNotFoundError(f"Input path not found: {input_path}")


def process_sds_file(
    pdf_path: Path,
    plugins: list[HazardListPlugin],
    synonym_table,
    master: dict,
) -> dict:
    """
    Process one SDS file, mutating `master` in place. Returns a small
    summary dict for CLI output. Extraction failures are reported, not
    raised — a corrupt or unreadable PDF in a batch directory must not
    abort processing of the rest of the batch (PROJECT_SPEC.md scope).
    """
    sds = extract_sds(pdf_path)
    summary = {
        "file": pdf_path.name,
        "product_name": sds.product_name,
        "extraction_error": sds.extraction_error,
        "components_found": 0,
        "unresolvable_count": 0,
        "list_hits": [],
    }

    if sds.extraction_error:
        return summary

    components = extract_components_for_sds(sds)
    summary["components_found"] = len(components)
    date_processed = date.today().isoformat()

    for row_index, component in enumerate(components):
        resolved = resolve_component(component, synonym_table)
        if resolved.match_key_type == "unresolvable":
            summary["unresolvable_count"] += 1

        hits = check_against_lists(resolved, plugins)
        key = component_key(resolved, sds.filename, row_index)
        product = ProductRef(
            product_name=sds.product_name,
            manufacturer=sds.manufacturer,
            sds_file=sds.filename,
            concentration_range=component.concentration_range,
            date_processed=date_processed,
        )
        upsert_component(master, key, resolved, product, hits)

        for list_id, hit in hits.items():
            if hit.listed:
                summary["list_hits"].append(
                    {"component": resolved.component.raw_name, "list_id": list_id}
                )

    return summary


def print_summary(file_summaries: list[dict]) -> None:
    for s in file_summaries:
        print(f"\n{s['file']}")
        if s["extraction_error"]:
            print(f"  FAILED TO EXTRACT: {s['extraction_error']} \u2014 flagged for manual review")
            continue

        product = s["product_name"] or "(product name not found)"
        print(f"  Product: {product}")
        print(
            f"  Components found: {s['components_found']} "
            f"(unresolvable: {s['unresolvable_count']})"
        )
        if s["list_hits"]:
            print("  Hazard list hits:")
            for hit in s["list_hits"]:
                print(f"    - {hit['component']}: listed on {hit['list_id']}")
        else:
            print("  No hazard list hits.")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sds-crossref",
        description=(
            "Batch SDS multi-list hazard cross-reference tool. "
            "Screening aid only \u2014 " + DISCLAIMER
        ),
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="A single SDS PDF, or a directory of SDS PDFs to process in batch.",
    )
    parser.add_argument(
        "--master-list",
        type=Path,
        default=Path("components_master.json"),
        help="Path to the persistent master component list (default: ./components_master.json)",
    )
    parser.add_argument(
        "--dispositions",
        type=Path,
        default=Path("dispositions.json"),
        help="Path to the disposition log (default: ./dispositions.json)",
    )
    parser.add_argument(
        "--epcra-tri-data",
        type=Path,
        default=None,
        help=(
            "Path to an EPA TRI chemical list CSV (chemical_name, cas_number "
            "columns). Required to enable EPCRA \u00a7313/TRI screening \u2014 see "
            "DATA_SOURCES_REFERENCE.md row 8."
        ),
    )
    parser.add_argument(
        "--epcra-tri-data-as-of",
        type=str,
        default="unknown",
        help="Date/version label for the EPCRA TRI data file, shown in every report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        sds_files = discover_sds_files(args.input_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not sds_files:
        print(f"No SDS PDF files found at {args.input_path}", file=sys.stderr)
        return 1

    try:
        plugins = build_plugins(args)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    synonym_table = load_default_synonym_table()
    master = load_master_list(args.master_list)
    dispositions = load_dispositions(args.dispositions)

    file_summaries = [
        process_sds_file(pdf_path, plugins, synonym_table, master)
        for pdf_path in sds_files
    ]

    apply_dispositions(master, dispositions)
    save_master_list(args.master_list, master)
    save_dispositions(args.dispositions, dispositions)

    print_summary(file_summaries)
    print(f"\nMaster list updated: {args.master_list} ({len(master)} components tracked)")
    print(f"\n{DISCLAIMER}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
