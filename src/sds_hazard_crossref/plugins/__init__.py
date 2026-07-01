"""
plugins — the hazard-list plugin registry.

Each regulatory/exposure list (Cal/OSHA PEL, NIOSH REL/IDLH, IARC, etc.) is
implemented as one module conforming to the HazardListPlugin interface
defined in `base.py`. See PROJECT_SPEC.md Section 6 for the list of
plugins planned, and DATA_SOURCES_REFERENCE.md for each source's access
method (automatable fetch / manual download / hand-maintained in-repo).

No concrete list plugins live here yet — this module currently holds only
the shared interface. Each plugin is a separate, reviewable increment
(see PROJECT_SPEC.md's "Working style": one hazard list module per PR).
"""

from .base import ListHit, HazardListPlugin

__all__ = ["ListHit", "HazardListPlugin"]
