from datetime import date
from decimal import Decimal

from ledgerlite.models import Entry


def test_roundtrip():
    e = Entry(day=date(2026, 3, 14), category="food", amount=Decimal("120.50"))
    assert Entry.from_dict(e.to_dict()) == e


def test_amount_is_decimal_not_float():
    e = Entry.from_dict({"day": "2026-01-01", "category": "x", "amount": "0.10", "currency": "INR"})
    assert e.amount + Decimal("0.20") == Decimal("0.30")


def test_currency_default():
    """Entry constructed without currency must default to INR."""
    e = Entry(day=date(2026, 1, 1), category="food", amount=Decimal("5"))
    assert e.currency == "INR"


def test_roundtrip_with_currency():
    """A non-default currency must survive to_dict -> from_dict unchanged."""
    e = Entry(day=date(2026, 6, 1), category="salary", amount=Decimal("3000"), currency="EUR")
    assert Entry.from_dict(e.to_dict()) == e
    assert Entry.from_dict(e.to_dict()).currency == "EUR"
