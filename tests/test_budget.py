from datetime import date
from decimal import Decimal

import pytest

from ledgerlite import budget
from ledgerlite.models import Entry


def _e(day_str: str, category: str, amount: str) -> Entry:
    return Entry(day=date.fromisoformat(day_str), category=category, amount=Decimal(amount))


# ---------------------------------------------------------------------------
# month_spent
# ---------------------------------------------------------------------------

def test_month_spent_sums_correctly():
    entries = [
        _e("2026-09-01", "food", "200"),
        _e("2026-09-15", "food", "300"),
        _e("2026-09-10", "transport", "120.50"),
    ]
    result = budget.month_spent(entries, 2026, 9)
    assert result["food"] == Decimal("500")
    assert result["transport"] == Decimal("120.50")


def test_month_spent_decimal_not_float():
    entries = [_e("2026-09-01", "food", "0.10")]
    result = budget.month_spent(entries, 2026, 9)
    assert isinstance(result["food"], Decimal)
    assert result["food"] + Decimal("0.20") == Decimal("0.30")


def test_month_spent_ignores_other_months():
    entries = [
        _e("2026-09-01", "food", "100"),
        _e("2026-10-01", "food", "999"),
        _e("2026-08-31", "food", "999"),
    ]
    result = budget.month_spent(entries, 2026, 9)
    assert result == {"food": Decimal("100")}


def test_month_spent_empty_returns_empty():
    assert budget.month_spent([], 2026, 9) == {}


# ---------------------------------------------------------------------------
# status_rows
# ---------------------------------------------------------------------------

def test_status_rows_under_budget():
    budgets = {"food": Decimal("5000")}
    spent = {"food": Decimal("3000")}
    rows = budget.status_rows(budgets, spent)
    assert len(rows) == 1
    row = rows[0]
    assert row["category"] == "food"
    assert row["budget"] == Decimal("5000")
    assert row["spent"] == Decimal("3000")
    assert row["remaining"] == Decimal("2000")


def test_status_rows_over_budget():
    """remaining is negative when spent exceeds budget."""
    budgets = {"food": Decimal("5000")}
    spent = {"food": Decimal("5200")}
    rows = budget.status_rows(budgets, spent)
    assert rows[0]["remaining"] == Decimal("-200")


def test_status_rows_no_budget_with_spending():
    """Category with spending but no budget appears with budget=None, remaining=None."""
    rows = budget.status_rows({}, {"food": Decimal("300")})
    assert len(rows) == 1
    row = rows[0]
    assert row["budget"] is None
    assert row["remaining"] is None
    assert row["spent"] == Decimal("300")


def test_status_rows_budget_no_spending():
    """Category with budget but no spending in the month appears with spent=0."""
    rows = budget.status_rows({"food": Decimal("5000")}, {})
    assert len(rows) == 1
    assert rows[0]["spent"] == Decimal("0")
    assert rows[0]["remaining"] == Decimal("5000")


def test_status_rows_excludes_no_budget_no_spend():
    """Category with neither budget nor spending must not appear."""
    budgets = {"food": Decimal("5000")}
    spent = {"food": Decimal("100"), "ghost": Decimal("0")}
    rows = budget.status_rows(budgets, spent)
    categories = [r["category"] for r in rows]
    # ghost has 0 spend and no budget — excluded
    assert "ghost" not in categories
    assert "food" in categories


# ---------------------------------------------------------------------------
# check_over_budget
# ---------------------------------------------------------------------------

def test_check_over_budget_fires():
    entries = [_e("2026-09-01", "food", "5200")]
    budgets = {"food": Decimal("5000")}
    result = budget.check_over_budget(budgets, entries, "food", 2026, 9)
    assert result is not None
    assert "food" in result
    assert "5200" in result
    assert "5000" in result


def test_check_over_budget_under_budget():
    entries = [_e("2026-09-01", "food", "4000")]
    budgets = {"food": Decimal("5000")}
    assert budget.check_over_budget(budgets, entries, "food", 2026, 9) is None


def test_check_over_budget_no_budget():
    """Returns None when no budget is set for the category."""
    entries = [_e("2026-09-01", "food", "99999")]
    assert budget.check_over_budget({}, entries, "food", 2026, 9) is None


def test_check_over_budget_exactly_at_limit():
    """Exactly at budget is not over — no warning."""
    entries = [_e("2026-09-01", "food", "5000")]
    budgets = {"food": Decimal("5000")}
    assert budget.check_over_budget(budgets, entries, "food", 2026, 9) is None


def test_check_over_budget_returns_string_not_none():
    """Return type is str when over, not a truthy non-string."""
    entries = [_e("2026-09-01", "food", "6000")]
    budgets = {"food": Decimal("5000")}
    result = budget.check_over_budget(budgets, entries, "food", 2026, 9)
    assert isinstance(result, str)
