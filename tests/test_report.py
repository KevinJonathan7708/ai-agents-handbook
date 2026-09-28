from datetime import date
from decimal import Decimal

import pytest

from ledgerlite import report
from ledgerlite.models import Entry


def _e(d, c, a):
    return Entry(date.fromisoformat(d), c, Decimal(a))


def test_month_range_mid_year():
    assert report.month_range(2026, 4) == (date(2026, 4, 1), date(2026, 4, 30))


def test_entries_in_month_includes_both_ends():
    entries = [
        _e("2026-04-01", "a", "1"),
        _e("2026-04-30", "a", "2"),
        _e("2026-05-01", "a", "4"),
    ]
    got = [e.amount for e in report.entries_in_month(entries, 2026, 4)]
    assert got == [Decimal("1"), Decimal("2")]


def test_totals_by_category_sorted():
    entries = [
        _e("2026-04-02", "food", "10"),
        _e("2026-04-03", "auto", "5"),
        _e("2026-04-04", "food", "2.5"),
    ]
    assert report.totals_by_category(entries) == {"auto": Decimal("5"), "food": Decimal("12.5")}


def test_format_report_has_total_line():
    out = report.format_report(2026, 4, {"food": Decimal("12.50")})
    assert out.splitlines()[0] == "Report 2026-04"
    assert out.splitlines()[-1].split() == ["TOTAL", "12.50"]


def test_month_range_december():
    # Issue #131: month_range(year, 12) raises ValueError because
    # date(year, 13, 1) is invalid. December must return Dec 1 – Dec 31.
    assert report.month_range(2026, 12) == (date(2026, 12, 1), date(2026, 12, 31))


# Characterization: every month of 2024 (a leap year — February has 29 days).
# Each tuple is (month, expected_last_day).
LEAP_YEAR_MONTHS = [
    (1,  31),
    (2,  29),  # 2024 is a leap year
    (3,  31),
    (4,  30),
    (5,  31),
    (6,  30),
    (7,  31),
    (8,  31),
    (9,  30),
    (10, 31),
    (11, 30),
    (12, 31),
]


@pytest.mark.parametrize("month,last_day", LEAP_YEAR_MONTHS)
def test_month_range_leap_year_2024(month, last_day):
    first, last = report.month_range(2024, month)
    assert first == date(2024, month, 1)
    assert last == date(2024, month, last_day)
