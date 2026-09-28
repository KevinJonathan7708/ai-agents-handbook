from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from .models import Entry

SCHEMA_VERSION = 3

# Maps a schema version to the function that upgrades a raw file dict to the next version.
MIGRATIONS: dict[int, Callable[[dict], dict]] = {}


def _migrate_v1_to_v2(data: dict) -> dict:
    """Add currency field (default "INR") to every entry that lacks it."""
    for entry in data.get("entries", []):
        entry["currency"] = "INR"
    return data


def _migrate_v2_to_v3(data: dict) -> dict:
    """Add top-level budgets map to files that pre-date this feature."""
    data.setdefault("budgets", {})
    return data


MIGRATIONS[1] = _migrate_v1_to_v2
MIGRATIONS[2] = _migrate_v2_to_v3


def _migrate(data: dict) -> dict:
    version = data.get("schema_version", 1)
    while version < SCHEMA_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
        data["schema_version"] = version
    return data


def load(path: Path) -> tuple[list[Entry], dict[str, Decimal]]:
    """Load entries and budgets. A missing file is an empty ledger. A corrupt file is an error."""
    if not path.exists():
        return [], {}
    data = json.loads(path.read_text(encoding="utf-8"))
    data = _migrate(data)
    entries = [Entry.from_dict(d) for d in data["entries"]]
    budgets = {k: Decimal(v) for k, v in data["budgets"].items()}
    return entries, budgets


def save(path: Path, entries: list[Entry], budgets: dict[str, Decimal]) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "budgets": {k: str(v) for k, v in budgets.items()},
        "entries": [e.to_dict() for e in entries],
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)
