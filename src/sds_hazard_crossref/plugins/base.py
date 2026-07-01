"""
base.py
The plugin contract every hazard list module implements (PROJECT_SPEC.md
Section 6: "each list is a plugin module implementing a common interface").

Adding a 13th list — including a non-California, non-US list for a user in
a different jurisdiction — should mean writing one new module against this
interface, not touching the matching engine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ListHit:
    """
    Result of checking one component against one hazard list.

    `listed` is always populated. Everything else is best-effort: a
    "not listed" result should still carry `source_citation` and
    `data_as_of` so a report never states "not listed" without also
    showing how current that determination is (PROJECT_SPEC.md Section 8).
    """

    list_id: str                  # e.g. "niosh_rel", "iarc", "epcra_302_ehs"
    listed: bool
    match_method: str             # "cas" | "name" | "check_required" | "unresolvable"
    source_citation: str          # human-readable source description
    data_as_of: str               # ISO date (or edition label) of the data snapshot checked
    details: dict[str, Any] = field(default_factory=dict)
    # List-specific extra fields — e.g. {"value": 50, "units": "ppm"} for a
    # PEL, {"tpq_lbs": 500} for EPCRA 302, {"group": "2A"} for IARC.
    note: str = ""
    # Free-text explanation for non-standard results, e.g. ACGIH's
    # "check required — not bundled, see licensing note" or an
    # "unresolvable — manual follow-up with supplier required" flag for a
    # CBI/trade-secret component with no CAS disclosed.


class HazardListPlugin(ABC):
    """
    Common interface for a single hazard/regulatory list.

    A plugin instance is loaded once per run (see `load()`) and then
    queried per component via `lookup()`. Implementations should never
    fabricate a match: if a component can't be confidently checked (e.g.
    ACGIH data isn't bundled, or the component has no CAS and no name
    match), return a ListHit with `listed=False` and `match_method` set to
    "check_required" or "unresolvable" as appropriate — never silently
    omit the list from the report.
    """

    #: Short, stable identifier used as the key in components_master.json's
    #: `list_hits` dict (see PROJECT_SPEC.md Section 5.1).
    list_id: str

    #: Human-readable name for reports, e.g. "NIOSH REL / IDLH".
    display_name: str

    @abstractmethod
    def load(self) -> None:
        """
        Load this list's data (from the in-repo bundled file, the local
        refresh cache, or a user-supplied path for check-only lists like
        ACGIH). Called once before any `lookup()` calls. Implementations
        should raise a clear, actionable error if the data isn't available
        rather than silently returning empty results.
        """

    @abstractmethod
    def lookup(self, cas: str | None, name: str | None) -> ListHit:
        """
        Check one component against this list. `cas` should already be
        normalized (see parser_core.normalize_cas); `name` should already
        be normalized (see parser_core.normalize_name) when provided as a
        fallback. At least one of `cas` or `name` will be provided by the
        matching engine — implementations should not assume both.
        """

    @abstractmethod
    def data_as_of(self) -> str:
        """
        The date (or edition label) of the data snapshot this plugin is
        currently using, for display in every report regardless of hit or
        miss (PROJECT_SPEC.md Section 8).
        """
