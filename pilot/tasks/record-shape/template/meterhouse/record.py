"""The reading record that every other module passes around.

A reading is one measurement of usage for one account.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Reading:
    account: str
    at: str
    quantity: Decimal
    unit: str

    def as_dict(self) -> dict:
        return {"account": self.account, "at": self.at,
                "quantity": str(self.quantity), "unit": self.unit}


def sort_key(reading: Reading) -> tuple:
    return (reading.account, reading.at)
