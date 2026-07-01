"""
epcra_313_tri_fetch.py
Fetches the current EPCRA \u00a7313/TRI chemical list from EPA's Envirofacts
DMAP REST API and writes it to a CSV in the format EPCRATriPlugin expects
(chemical_name, cas_number columns).

IMPORTANT \u2014 read before trusting this fetcher's output:
The endpoint scheme and pagination style (`/dmapservice/[table]/[first]:
[last]/JSON`) were confirmed live and working during development, against
a sibling table in the same API (tri.tri_facility returned real facility
records). The exact column names on the tri_chem_info table itself were
NOT independently verified against a live response \u2014 the development
environment could not reach data.epa.gov to test that specific call. This
fetcher is deliberately defensive as a result: it tries several plausible
column-name candidates (in EPA's documented snake_case convention) and
raises a clear, actionable error showing the actual keys returned if none
of them match, rather than silently writing an empty or incorrect CSV.

Run this once against the live API and confirm the output looks right
before relying on it for real screening. If it fails on the column-name
step, the error message will show you the real field names \u2014 update
_NAME_FIELD_CANDIDATES / _CAS_FIELD_CANDIDATES here to match and re-run.
"""

import csv
import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import truststore

_BASE_URL = "https://data.epa.gov/dmapservice/tri.tri_chem_info"
_PAGE_SIZE = 500
# The TRI list has ~860 chemicals/categories as of this writing; this caps
# pagination well above that so a live run can't loop indefinitely if the
# API's "no more rows" signal doesn't behave as expected.
_MAX_PAGES = 5

_NAME_FIELD_CANDIDATES = ("chem_name", "chemical_name", "tri_chem_name")
_CAS_FIELD_CANDIDATES = ("cas_number", "cas_registry_number", "chem_id", "cas_reg_number")

# Built once at import time. truststore defers certificate verification to
# the operating system's native trust store (macOS Keychain, Windows
# Certificate Store, or the system's OpenSSL config on Linux) instead of a
# bundled public-CA-only file. This matters on managed/corporate networks
# that route HTTPS through a TLS-inspecting proxy: IT typically installs
# that proxy's root certificate into the OS trust store via MDM, and a
# bundled-file approach (like certifi) has no way to know about it. Using
# the OS's own store is what browsers already do, so this makes the
# fetcher behave consistently with them regardless of network setup \u2014
# still no OS-specific code written here; truststore handles that
# abstraction internally and supports macOS/Windows/Linux.
_SSL_CONTEXT = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


class TriFetchError(RuntimeError):
    pass


@dataclass
class FetchResult:
    rows_written: int
    category_only_rows: int
    output_path: Path
    raw_cache_path: Path


def fetch_epcra_313_tri(
    output_csv: Path, raw_cache_path: Path, timeout: int = 30
) -> FetchResult:
    """
    Pull the full TRI chemical list and write it to `output_csv`. The raw
    JSON response is always cached to `raw_cache_path` first \u2014 even if
    column-name identification fails afterward \u2014 so a failed run still
    leaves you with the real data to inspect and fix the field mapping
    against, rather than nothing.
    """
    all_rows = _fetch_all_pages(timeout)

    if not all_rows:
        raise TriFetchError(
            "EPA API returned no rows for tri.tri_chem_info. The table "
            "name or endpoint may have changed \u2014 verify at "
            "https://www.epa.gov/enviro/web-services before retrying."
        )

    raw_cache_path.parent.mkdir(parents=True, exist_ok=True)
    raw_cache_path.write_text(json.dumps(all_rows, indent=2), encoding="utf-8")

    name_field = _first_present_field(all_rows[0], _NAME_FIELD_CANDIDATES)
    cas_field = _first_present_field(all_rows[0], _CAS_FIELD_CANDIDATES)
    if name_field is None or cas_field is None:
        raise TriFetchError(
            "Could not identify the chemical-name / CAS-number columns in "
            "the API response (see this module's docstring \u2014 the exact "
            "field names weren't verified against a live response during "
            f"development). Actual keys returned: {sorted(all_rows[0].keys())}. "
            "Update _NAME_FIELD_CANDIDATES / _CAS_FIELD_CANDIDATES in "
            "epcra_313_tri_fetch.py to match, then re-run. Raw response "
            f"cached at {raw_cache_path} for inspection."
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    category_only = 0
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["chemical_name", "cas_number"])
        for row in all_rows:
            name = (row.get(name_field) or "").strip()
            cas = (row.get(cas_field) or "").strip()
            if not name:
                continue
            if not cas:
                category_only += 1
            writer.writerow([name, cas])

    return FetchResult(
        rows_written=len(all_rows),
        category_only_rows=category_only,
        output_path=output_csv,
        raw_cache_path=raw_cache_path,
    )


def _fetch_all_pages(timeout: int) -> list[dict]:
    all_rows: list[dict] = []
    for page in range(_MAX_PAGES):
        start = page * _PAGE_SIZE + 1
        end = start + _PAGE_SIZE - 1
        url = f"{_BASE_URL}/{start}:{end}/JSON"
        try:
            with urllib.request.urlopen(url, timeout=timeout, context=_SSL_CONTEXT) as response:
                batch = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise TriFetchError(f"Failed to fetch {url}: {e}") from e

        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < _PAGE_SIZE:
            break
    return all_rows


def _first_present_field(sample_row: dict, candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in sample_row:
            return candidate
    return None
