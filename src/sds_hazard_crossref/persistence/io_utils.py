"""
io_utils.py
Atomic JSON read/write, shared by master_list.py and dispositions.py.

Writes go to a temp file in the same directory, then `os.replace()` swaps
it into place. `os.replace` is atomic on both POSIX and Windows (unlike
`os.rename`, which historically wasn't guaranteed atomic-with-overwrite on
Windows) — this means a crash or interrupted run mid-write can never leave
components_master.json or dispositions.json half-written/corrupted; the
reader always sees either the old complete file or the new complete file,
never a partial one. All paths handled via pathlib per the project's
cross-platform requirement — no OS-specific path handling.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file, returning {} if it doesn't exist yet (first run)."""
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
