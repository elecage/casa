"""The reading record that every other module passes around.

A reading is one measurement of usage for one account. It carries both
timestamps the feeds give us (`docs/v04-corrections.md`) and where it came
from (`docs/v05-audit.md`).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Reading:
    id: str
    account: str
    observed_at: str
    recorded_at: str
    quantity: Decimal
    unit: str
    corrects: str | None
    source_file: str
    source_line: int

    @property
    def at(self) -> str:
        """When the usage happened. Kept for callers that only need one."""
        return self.observed_at

    def as_dict(self) -> dict:
        return {"id": self.id, "account": self.account,
                "observed_at": self.observed_at,
                "recorded_at": self.recorded_at,
                "quantity": str(self.quantity), "unit": self.unit,
                "corrects": self.corrects,
                "source": {"file": self.source_file,
                           "line": self.source_line}}


def sort_key(reading: Reading) -> tuple:
    return (reading.account, reading.observed_at, reading.recorded_at)
