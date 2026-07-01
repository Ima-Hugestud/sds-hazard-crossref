"""
master_list.py
Load/save/merge logic for components_master.json — the persistent
inventory of every chemical/product combination processed over time
(PROJECT_SPEC.md Section 5.1).

Merge policy, made explicit here rather than left implicit in code:
  - `primary_name` is set once, on first sight, and never overwritten —
    later name variants for the same key go into `synonyms` instead, so
    the master list doesn't flip its display name every time a slightly
    differently-worded SDS gets processed.
  - `products` entries are upserted (matched on sds_file + product_name)
    so re-processing the same SDS updates that product's record in place
    rather than appending a duplicate.
  - `list_hits` are overwritten with each run's fresh determination — the
    master list always reflects the most recent screening, not a stale
    one. Human review decisions live in dispositions.json and are layered
    back on top separately (see dispositions.py: `apply_dispositions`),
    so a re-run's fresh list_hits never silently erase a reviewer's prior
    judgment call.
"""

from dataclasses import asdict, dataclass
from pathlib import Path

from ..matching.engine import ResolvedComponent
from ..plugins.base import ListHit
from .io_utils import load_json, save_json


@dataclass
class ProductRef:
    product_name: str | None
    manufacturer: str | None
    sds_file: str
    concentration_range: str | None
    date_processed: str


def load_master_list(path: Path) -> dict:
    return load_json(path)


def save_master_list(path: Path, master: dict) -> None:
    save_json(path, master)


def upsert_component(
    master: dict,
    key: str,
    resolved: ResolvedComponent,
    product_ref: ProductRef,
    list_hits: dict[str, ListHit],
) -> None:
    """Merge one resolved component's data into `master` in place."""
    entry = master.get(key)
    if entry is None:
        entry = {
            "primary_name": resolved.component.raw_name or None,
            "cas": resolved.cas,
            "synonyms": [],
            "products": [],
            "list_hits": {},
            "disposition": {
                "status": "unreviewed",
                "reviewer": None,
                "notes": "",
                "last_updated": None,
            },
        }
        master[key] = entry

    raw_name = resolved.component.raw_name
    if raw_name and raw_name != entry["primary_name"] and raw_name not in entry["synonyms"]:
        entry["synonyms"].append(raw_name)

    products = entry["products"]
    match = next(
        (
            p for p in products
            if p["sds_file"] == product_ref.sds_file
            and p["product_name"] == product_ref.product_name
        ),
        None,
    )
    if match is not None:
        match.update(asdict(product_ref))
    else:
        products.append(asdict(product_ref))

    for list_id, hit in list_hits.items():
        entry["list_hits"][list_id] = asdict(hit)
