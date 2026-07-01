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

TRI includes ~38 chemical *categories* (e.g. "Antimony compounds",
"Certain glycol ethers") alongside individually-CAS-numbered substances.
EPA's data represents these with an internal category code (e.g. "N010")
in the same field individual entries use for a CAS number — never a real
CAS, and never blank in practice, though this plugin also handles a truly
blank field defensively. `normalize_cas()` correctly rejects a category
code as not CAS-shaped, so these entries get a separate lookup path:
matched only by an *exact* normalized-name match against the category's
own listed name (e.g. a component literally named "Antimony compounds" on
an SDS), never fuzzy-matched against individual substances in that
category. `ListHit.match_method` is "category_name" for these — distinct
from "cas" and "name" — so a report never implies CAS-level confidence for
what is, by definition, a broader category-level determination.
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
        self._category_by_name: dict[str, dict] = {}  # normalized name -> {category_code, chemical_name}
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
                    # A truly blank CAS field with a name still present.
                    # Not observed in practice against the live EPA data
                    # (category entries carry a code, not a blank — see
                    # below), but handled defensively rather than assumed
                    # away.
                    self._category_by_name[normalize_name(name)] = {
                        "category_code": None,
                        "chemical_name": name,
                    }
                    self._category_only_count += 1
                    continue

                cas = normalize_cas(raw_cas)
                if cas is not None:
                    self._by_cas[cas] = name
                    self._by_name[normalize_name(name)] = cas
                    continue

                # Present but not CAS-shaped -> a TRI chemical *category*
                # entry, keyed by EPA's own category code (e.g. "N010").
                # Never treated as or confused with a CAS number.
                self._category_by_name[normalize_name(name)] = {
                    "category_code": raw_cas,
                    "chemical_name": name,
                }
                self._category_only_count += 1

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
            normalized = normalize_name(name)

            matched_cas = self._by_name.get(normalized)
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

            category = self._category_by_name.get(normalized)
            if category:
                code = category["category_code"] or "not provided in source data"
                return ListHit(
                    list_id=self.list_id,
                    listed=True,
                    match_method="category_name",
                    source_citation=_SOURCE_CITATION,
                    data_as_of=self._data_as_of_value,
                    details={
                        "tri_listed_name": category["chemical_name"],
                        "tri_category_code": category["category_code"],
                    },
                    note=(
                        "Matched as a TRI chemical CATEGORY, not an individually "
                        "CAS-numbered substance — no single CAS number applies. "
                        f"Matched by exact normalized name against EPA's category "
                        f'"{category["chemical_name"]}" (EPA category code: {code}). '
                        "Category-level matches carry lower confidence than a CAS "
                        "match and should be verified against the source SDS."
                    ),
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
