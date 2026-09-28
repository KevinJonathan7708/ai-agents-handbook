from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Entry:
    """One ledger line. Amounts are Decimal, never float."""

    day: date
    category: str
    amount: Decimal
    currency: str = "INR"

    def to_dict(self) -> dict:
        return {
            "day": self.day.isoformat(),
            "category": self.category,
            "amount": str(self.amount),
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Entry:
        # currency is required — a KeyError here means a missing migration, not a missing default.
        return cls(
            day=date.fromisoformat(d["day"]),
            category=d["category"],
            amount=Decimal(d["amount"]),
            currency=d["currency"],
        )
