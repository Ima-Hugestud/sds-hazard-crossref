"""
refresh_cli.py
CLI entry point: `sds-crossref-refresh-data`.

A separate command from `sds-crossref` (deliberately \u2014 keeps this a
small, reviewable increment that can't affect the already-tested main
processing CLI). Currently supports one source:

    sds-crossref-refresh-data --list epcra-313-tri --output tri_data.csv

See refresh/epcra_313_tri_fetch.py's module docstring for an important
caveat: this fetcher's column-name mapping was not verified against a
live API response during development. Run it, check the output, and
report back if it fails \u2014 the error message will show the real column
names if the current guesses are wrong.
"""

import argparse
import sys
from pathlib import Path

from .refresh.epcra_313_tri_fetch import TriFetchError, fetch_epcra_313_tri

_SOURCES = {"epcra-313-tri"}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sds-crossref-refresh-data",
        description="Fetch current data for an automatable hazard list source.",
    )
    parser.add_argument(
        "--list",
        required=True,
        choices=sorted(_SOURCES),
        help="Which hazard list to refresh.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Where to write the resulting CSV (consumed by the matching plugin).",
    )
    parser.add_argument(
        "--raw-cache",
        type=Path,
        default=None,
        help=(
            "Where to cache the raw API response (default: alongside --output, "
            "same name with a .raw.json suffix). Kept even if CSV writing fails, "
            "so a failed run still leaves you the real data to inspect."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    raw_cache = args.raw_cache or args.output.with_suffix(".raw.json")

    if args.list == "epcra-313-tri":
        try:
            result = fetch_epcra_313_tri(output_csv=args.output, raw_cache_path=raw_cache)
        except TriFetchError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        print(f"Wrote {result.rows_written} rows to {result.output_path}")
        if result.category_only_rows:
            print(
                f"  ({result.category_only_rows} of those are category-level "
                f"entries with no single CAS number \u2014 these won't be matchable "
                f"via the CAS-primary engine; see PROJECT_SPEC.md \u00a77)"
            )
        print(f"Raw API response cached at {result.raw_cache_path}")
        return 0

    # Unreachable while _SOURCES has one entry, but kept explicit for when
    # a second source is added.
    print(f"Error: unknown list '{args.list}'", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
