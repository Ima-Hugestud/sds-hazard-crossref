"""
epcra_313_tri.py
Plugin for the EPCRA Section 313 Toxics Release Inventory (TRI) chemical
list.

Per DATA_SOURCES_REFERENCE.md row 8, this is the strongest-verified source
in the whole registry: EPA publishes genuine bulk CSV "Basic Data Files"
and a free, no-auth Envirofacts REST API — this is the one list in the
registry where a real `--refresh-data` automated pull is fully justified
(not yet implemented; see the module docstring note below).

IMPORTANT: this plugin loads from an explicitly-provided CSV path. There
is no bundled "default" data file, and none should ever be added here from
memory — TRI list membership is exactly the kind of regulatory fact that
must come from a verified source, never guessed or reconstructed from
general knowledge. The only file currently checked into this repo is
tests/fixtures/epcra_313_tri_TEST_FIXTURE.csv, a handful of chemicals that
are unambiguous, long-standing TRI entries, explicitly labeled as a test
fixture — not a production dataset. Populating a real data file is a
`--refresh-data` task (pulling EPA's actual bulk CSV or Envirofacts API),
not something to fabricate here.
"""

import csv
from pathlib import Path

from ..parser_core.cas import normalize_cas
from ..parser_core.names import normalize_name
from .base import HazardListPlugin, ListHit

_SOURCE_CITATION = (
    "EPA EPCRA Section 313 Toxics Release Inventory (TRI) Chemical List"
)


class EPCRATriPlugin(HazardListPlugin):
    list_id = "epcra_313_tri"
    display_name = "EPCRA §313 Toxics Release Inventory (TRI) Chemical List"

    def __init__(self, data_path: Path, data_as_of: str):
        """
        `data_path`: CSV with columns `chemical_name`, `cas_number` (blank
        for category-level entries — see `load()`).
        `data_as_of`: the date/version label of that CSV, shown on every
        report regardless of hit or miss (PROJECT_SPEC.md Section 8).
        """
        self._data_path = Path(data_path)
        self._data_as_of_value = data_as_of
        self._by_cas: dict[str, str] = {}  # cas -> chemical_name
        self._by_name: dict[str, str] = {}  # normalized name -> cas
        self._category_only_count = 0
        self._loaded = False

    def load(self) -> None:
        if not self._data_path.exists():
            raise FileNotFoundError(
                f"EPCRA §313/TRI data file not found: {self._data_path}. "
                f"This plugin requires a real EPA TRI chemical list CSV — "
                f"see DATA_SOURCES_REFERENCE.md row 8 for the source."
            )

        with self._data_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_cas = (row.get("cas_number") or "").strip()
                name = (row.get("chemical_name") or "").strip()
                if not name:
                    continue

                if not raw_cas:
                    # TRI includes chemical *categories* with no single CAS
                    # (e.g. "Xylene (mixed isomers)" style category
                    # entries). These can't be matched via the CAS-primary
                    # engine; counted so load() can report coverage
                    # honestly rather than silently dropping them.
                    self._category_only_count += 1
                    continue

                cas = normalize_cas(raw_cas)
                if cas is None:
                    continue

                self._by_cas[cas] = name
                self._by_name[normalize_name(name)] = cas

        self._loaded = True

    def lookup(self, cas: str | None, name: str | None) -> ListHit:
        if not self._loaded:
            raise RuntimeError("EPCRATriPlugin.lookup() called before load()")

        if cas and cas in self._by_cas:
            return ListHit(
                list_id=self.list_id,
                listed=True,
                match_method="cas",
                source_citation=_SOURCE_CITATION,
                data_as_of=self._data_as_of_value,
                details={"tri_listed_name": self._by_cas[cas]},
            )

        if name:
            matched_cas = self._by_name.get(normalize_name(name))
            if matched_cas:
                return ListHit(
                    list_id=self.list_id,
                    listed=True,
                    match_method="name",
                    source_citation=_SOURCE_CITATION,
                    data_as_of=self._data_as_of_value,
                    details={"tri_listed_name": self._by_cas[matched_cas]},
                    note="Matched by name only — no CAS was available to confirm.",
                )

        return ListHit(
            list_id=self.list_id,
            listed=False,
            match_method="cas" if cas else "name",
            source_citation=_SOURCE_CITATION,
            data_as_of=self._data_as_of_value,
        )

    def data_as_of(self) -> str:
        return self._data_as_of_value
