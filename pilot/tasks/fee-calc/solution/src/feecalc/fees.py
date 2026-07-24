"""Reference solution for the fee-calc task (grading/calibration only,
never shipped to sessions)."""

from __future__ import annotations

_TIERS = ((100.0, 0.0), (500.0, 0.02), (2000.0, 0.015), (float("inf"), 0.01))
_BASE = 5.0


def fee(amount: float) -> float:
    total = _BASE
    lower = 0.0
    for upper, rate in _TIERS:
        if amount <= lower:
            break
        span = min(amount, upper) - lower
        total += span * rate
        lower = upper
    return round(total, 2)
