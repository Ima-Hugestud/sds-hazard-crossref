"""
component_key.py
Derives the key used to store/merge a component in components_master.json.

PROJECT_SPEC.md Section 5.1 says the master list is "keyed by CAS number
(or a normalized-name key when no CAS is available/disclosed)." That's
correct for a component that genuinely lacks a CAS but still has a real,
specific name (e.g. a manufacturer just omitted it by oversight). It is
NOT safe for trade-secret/CBI entries: "Proprietary amine blend" from two
different manufacturers is placeholder text, not a real chemical name —
treating it as a name key would silently merge two unrelated, unidentified
substances into a single master-list record. Unresolvable components
instead get a synthetic key scoped to the specific SDS and row they came
from, so they're tracked (and reviewable) without ever being conflated
with another product's differently-unidentified component.
"""

from ..matching.engine import ResolvedComponent


def component_key(resolved: ResolvedComponent, sds_filename: str, row_index: int) -> str:
    """
    `sds_filename` and `row_index` (the component's position within that
    SDS's parsed component list) are only used for the unresolvable case,
    to keep synthetic keys stable across re-runs of the same file while
    still being unique per-product.
    """
    if resolved.match_key_type == "cas":
        return resolved.cas
    if resolved.match_key_type == "name":
        return f"name::{resolved.normalized_name}"
    return f"unresolved::{sds_filename}::{row_index}"
