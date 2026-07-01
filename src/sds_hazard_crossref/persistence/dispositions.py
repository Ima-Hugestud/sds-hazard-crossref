"""
dispositions.py
Load/save logic for dispositions.json — a human reviewer's sign-off on
ambiguous or borderline matches, tracked separately from
components_master.json so it survives that file being regenerated on every
run (PROJECT_SPEC.md Section 5.2).

Two levels of disposition, matching how review actually happens in
practice:
  - Component-level: an overall status for the component as a whole
    (e.g. "reviewed", "needs_review").
  - List-level: a judgment call about one specific list hit — this is
    where the spec's own example lives ("listed on EPCRA 313 but below
    our facility's reportable threshold, no action needed"). That's a
    decision about one list, not the whole component, so it's tracked per
    (component_key, list_id) rather than flattened into a single
    component-wide note.

`apply_dispositions` is the only thing that writes disposition data into
the master list's in-memory representation — components_master.json's
"disposition" fields are always a mirror of dispositions.json, populated
at write time, never edited directly. That keeps a single source of truth
for review decisions.
"""

from pathlib import Path
from typing import Any

from .io_utils import load_json, save_json


def load_dispositions(path: Path) -> dict:
    return load_json(path)


def save_dispositions(path: Path, dispositions: dict) -> None:
    save_json(path, dispositions)


def record_component_disposition(
    dispositions: dict,
    key: str,
    status: str,
    reviewer: str | None,
    notes: str,
    last_updated: str,
) -> None:
    entry = dispositions.setdefault(key, {"list_dispositions": {}})
    entry["component_status"] = status
    entry["reviewer"] = reviewer
    entry["notes"] = notes
    entry["last_updated"] = last_updated


def record_list_disposition(
    dispositions: dict,
    key: str,
    list_id: str,
    status: str,
    reviewer: str | None,
    notes: str,
    last_updated: str,
) -> None:
    entry = dispositions.setdefault(key, {"list_dispositions": {}})
    entry.setdefault("list_dispositions", {})[list_id] = {
        "status": status,
        "reviewer": reviewer,
        "notes": notes,
        "last_updated": last_updated,
    }


def apply_dispositions(master: dict[str, Any], dispositions: dict[str, Any]) -> None:
    """
    Layer stored review decisions from `dispositions` back onto `master`,
    in place. Call this after re-populating master's list_hits for the
    current run, so a fresh "not listed" determination doesn't silently
    wipe out a reviewer's prior note about that same list hit.
    """
    for key, entry in master.items():
        disp = dispositions.get(key)
        if disp is None:
            continue

        if "component_status" in disp:
            entry["disposition"] = {
                "status": disp.get("component_status", "unreviewed"),
                "reviewer": disp.get("reviewer"),
                "notes": disp.get("notes", ""),
                "last_updated": disp.get("last_updated"),
            }

        list_dispositions = disp.get("list_dispositions", {})
        for list_id, list_disp in list_dispositions.items():
            hit = entry.get("list_hits", {}).get(list_id)
            if hit is not None:
                hit["disposition"] = list_disp
