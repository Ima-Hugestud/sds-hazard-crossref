"""
plugins — the hazard-list plugin registry.

Each regulatory/exposure list (Cal/OSHA PEL, NIOSH REL/IDLH, IARC, etc.) is
implemented as one module conforming to the HazardListPlugin interface
defined in `base.py`. See PROJECT_SPEC.md Section 6 for the list of
plugins planned, and DATA_SOURCES_REFERENCE.md for each source's access
method (automatable fetch / manual download / hand-maintained in-repo).

No concrete list plugins live here yet, aside from EPCRATriPlugin (EPCRA
§313/TRI — the strongest-verified automatable source in the registry, see
DATA_SOURCES_REFERENCE.md row 8). Each additional plugin is a separate,
reviewable increment (see PROJECT_SPEC.md's "Working style": one hazard
list module per PR).
"""

from .base import ListHit, HazardListPlugin
from .epcra_313_tri import EPCRATriPlugin

__all__ = ["ListHit", "HazardListPlugin", "EPCRATriPlugin"]
