import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ledgerlite import store
from ledgerlite.models import Entry

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_missing_file_is_empty(tmp_path):
    entries, budgets = store.load(tmp_path / "nope.json")
    assert entries == []
    assert budgets == {}


def test_save_then_load(tmp_path):
    p = tmp_path / "ledger.json"
    entries = [
        Entry(date(2026, 1, 5), "rent", Decimal("15000")),
        Entry(date(2026, 1, 6), "food", Decimal("250.25")),
    ]
    store.save(p, entries, {})
    loaded_entries, loaded_budgets = store.load(p)
    assert loaded_entries == entries
    assert loaded_budgets == {}


def test_corrupt_file_raises(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        store.load(p)


def test_migrate_v1_fixture(tmp_path):
    """A v1 file (no currency key) must load with currency='INR' and be saved as schema v3."""
    entries, budgets = store.load(FIXTURES_DIR / "ledger_v1.json")
    assert len(entries) == 2
    for entry in entries:
        assert entry.currency == "INR"
    assert budgets == {}

    out = tmp_path / "migrated.json"
    store.save(out, entries, budgets)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == 3


def test_migrate_v2_fixture(tmp_path):
    """A v2 file (no budgets key) must load with budgets={} and be saved as schema v3."""
    entries, budgets = store.load(FIXTURES_DIR / "ledger_v2.json")
    assert len(entries) == 2
    assert budgets == {}

    out = tmp_path / "migrated.json"
    store.save(out, entries, budgets)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == 3


def test_save_then_load_with_currency(tmp_path):
    """Non-default currency must survive a save/load round-trip unchanged."""
    p = tmp_path / "ledger.json"
    entries = [
        Entry(date(2026, 3, 1), "travel", Decimal("5000"), "USD"),
        Entry(date(2026, 3, 2), "hotel", Decimal("8000"), "EUR"),
    ]
    store.save(p, entries, {})
    loaded_entries, _ = store.load(p)
    assert loaded_entries[0].currency == "USD"
    assert loaded_entries[1].currency == "EUR"


def test_save_then_load_with_budgets(tmp_path):
    """Budgets must survive a save/load round-trip as Decimal."""
    p = tmp_path / "ledger.json"
    budgets = {"food": Decimal("5000"), "transport": Decimal("2000.50")}
    store.save(p, [], budgets)
    _, loaded_budgets = store.load(p)
    assert loaded_budgets == budgets
    for v in loaded_budgets.values():
        assert isinstance(v, Decimal)
