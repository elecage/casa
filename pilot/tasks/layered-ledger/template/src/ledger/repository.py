"""Account store — persists balances through the serialization boundary.

Invariant (holds everywhere): balances are stored in their serialized
(string) form and reconstructed via serialize.py, so nothing bypasses the
boundary. Callers get Money back, never raw strings.
"""

from __future__ import annotations

from .money import Money
from .serialize import format_money, parse_money


class AccountRepository:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def save(self, account_id: str, balance: Money) -> None:
        self._store[account_id] = format_money(balance)

    def load(self, account_id: str) -> Money:
        return parse_money(self._store[account_id])

    def has(self, account_id: str) -> bool:
        return account_id in self._store
