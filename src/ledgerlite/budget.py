from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from . import store
from .models import Entry


def month_spent(entries: list[Entry], year: int, month: int) -> dict[str, Decimal]:
    """Return total Decimal spend per category for the given calendar month."""
    totals: dict[str, Decimal] = {}
    for e in entries:
        if e.day.year == year and e.day.month == month:
            totals[e.category] = totals.get(e.category, Decimal(0)) + e.amount
    return totals


def status_rows(
    budgets: dict[str, Decimal],
    spent: dict[str, Decimal],
) -> list[dict]:
    """
    Return one row per category that has a budget OR has non-zero spending.
    Each row: {category, budget, spent, remaining}.
    budget and remaining are Decimal or None (caller renders None as '—').
    remaining = budget - spent; negative means over-budget.
    """
    categories = set(budgets.keys()) | {k for k, v in spent.items() if v != Decimal(0)}
    rows = []
    for cat in sorted(categories):
        b = budgets.get(cat)
        s = spent.get(cat, Decimal(0))
        remaining = (b - s) if b is not None else None
        rows.append({"category": cat, "budget": b, "spent": s, "remaining": remaining})
    return rows


def check_over_budget(
    budgets: dict[str, Decimal],
    entries: list[Entry],
    category: str,
    year: int,
    month: int,
) -> str | None:
    """
    Return a warning string if category's month-to-date spend exceeds its budget,
    or None if not over budget or no budget is set.
    Never prints; the caller decides where the string goes.
    """
    if category not in budgets:
        return None
    b = budgets[category]
    totals = month_spent(entries, year, month)
    s = totals.get(category, Decimal(0))
    if s > b:
        return f"Warning: {category} is over budget (spent {s}, budget {b})"
    return None


def set_budget(ledger: Path, category: str, amount: Decimal) -> None:
    """Persist a budget for category. Overwrites any existing value. Atomic write."""
    entries, budgets = store.load(ledger)
    budgets[category] = amount
    store.save(ledger, entries, budgets)
