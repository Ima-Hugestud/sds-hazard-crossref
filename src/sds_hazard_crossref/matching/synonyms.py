"""
synonyms.py
Loads and queries the human-curated name -> CAS synonym table used by the
name-based fallback matcher (see PROJECT_SPEC.md Section 7).

Deliberately a thin wrapper around a plain dict: every entry is a curated,
verified equivalence a human asserted (see data/name_synonyms.json), not
something inferred algorithmically. Keeping this separate from
`parser_core.names.normalize_name` (which only normalizes formatting) is
what keeps every name-based CAS match traceable to a specific, reviewable
claim rather than a heuristic.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..parser_core.names import normalize_name

_DEFAULT_SYNONYM_FILE = Path(__file__).parent.parent / "data" / "name_synonyms.json"


@dataclass
class SynonymTable:
    # normalized name -> CAS
    _table: dict[str, str] = field(default_factory=dict)

    def lookup(self, name: str) -> str | None:
        """Return the CAS number for a known synonym, or None if the
        (already-normalized-by-caller-or-not) name isn't in the table."""
        return self._table.get(normalize_name(name))

    def __len__(self) -> int:
        return len(self._table)


def load_default_synonym_table(path: Path | None = None) -> SynonymTable:
    """
    Load the in-repo synonym table. `path` defaults to
    `data/name_synonyms.json`; pass an alternate path for testing or to
    layer in a user-maintained supplemental table.
    """
    target = path or _DEFAULT_SYNONYM_FILE
    raw = json.loads(Path(target).read_text(encoding="utf-8"))
    table = {k: v for k, v in raw.items() if not k.startswith("_")}
    return SynonymTable(_table=table)
