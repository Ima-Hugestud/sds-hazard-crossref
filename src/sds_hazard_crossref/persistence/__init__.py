"""
persistence — components_master.json and dispositions.json read/write and
merge logic (PROJECT_SPEC.md Section 5).
"""

from .component_key import component_key
from .master_list import ProductRef, load_master_list, save_master_list, upsert_component
from .dispositions import (
    load_dispositions,
    save_dispositions,
    record_component_disposition,
    record_list_disposition,
    apply_dispositions,
)

__all__ = [
    "component_key",
    "ProductRef",
    "load_master_list",
    "save_master_list",
    "upsert_component",
    "load_dispositions",
    "save_dispositions",
    "record_component_disposition",
    "record_list_disposition",
    "apply_dispositions",
]
