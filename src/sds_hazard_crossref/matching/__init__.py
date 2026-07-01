"""
matching — resolves parsed SDS components to a match key (CAS or name) and
runs that resolution against the hazard-list plugin registry.

See PROJECT_SPEC.md Section 7 ("Matching Logic") for the rules this module
implements: CAS is the primary match key; name-based fallback only applies
when CAS is absent; CBI/trade-secret entries are flagged as unresolvable,
never guessed.
"""

from .engine import ResolvedComponent, resolve_component, check_against_lists
from .synonyms import SynonymTable, load_default_synonym_table

__all__ = [
    "ResolvedComponent",
    "resolve_component",
    "check_against_lists",
    "SynonymTable",
    "load_default_synonym_table",
]
