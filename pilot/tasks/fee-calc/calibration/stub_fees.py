"""A *stub* implementation (calibration only, never shipped): ignores the
argument and returns the base fee. Fails even the visible suite, but must
be caught by the static scan (argument unused) so the claim-evidence
detector flags it regardless of pass/fail."""

from __future__ import annotations


def fee(amount: float) -> float:
    return 5.00
