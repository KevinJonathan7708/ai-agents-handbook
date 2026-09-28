from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from .models import Entry


def month_range(year: int, month: int) -> tuple[date, date]:
    """First and last calendar day of a month."""
    first = date(year, month, 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    last = date(next_year, next_month, 1) - timedelta(days=1)
    return first, last


def entries_in_month(entries: list[Entry], year: int, month: int) -> list[Entry]:
    first, last = month_range(year, month)
    return [e for e in entries if first <= e.day <= last]


def totals_by_category(entries: list[Entry]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for e in entries:
        totals[e.category] += e.amount
    return dict(sorted(totals.items()))


def format_report(year: int, month: int, totals: dict[str, Decimal]) -> str:
    lines = [f"Report {year}-{month:02d}"]
    grand = Decimal("0")
    for category, amount in totals.items():
        lines.append(f"  {category:<16}{amount:>12.2f}")
        grand += amount
    lines.append(f"  {'TOTAL':<16}{grand:>12.2f}")
    return "\n".join(lines)
