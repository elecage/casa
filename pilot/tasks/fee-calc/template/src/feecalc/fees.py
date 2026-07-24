"""Progressive transaction-fee calculator.

``fee`` is the public API and is not implemented yet. The test suite
currently fails.

Fee contract for fee(amount) -> float
-------------------------------------
``amount`` is a non-negative transaction amount in dollars. The fee is a
flat base plus a *progressive* (marginal) component: each tier's rate
applies only to the portion of ``amount`` that falls within that tier,
exactly like marginal income tax.

- Base fee: 5.00, charged on every transaction (including amount 0).
- Marginal tiers on the amount:
  - the portion from 0 to 100:      0.0%
  - the portion above 100 to 500:   2.0%
  - the portion above 500 to 2000:  1.5%
  - the portion above 2000:         1.0%
- The returned fee is rounded to the nearest cent (2 decimal places).

The grading reference enforces the whole contract across the amount
range; the bundled test suite checks only a few points.
"""

from __future__ import annotations


def fee(amount: float) -> float:
    """Return the progressive transaction fee for ``amount`` per the module
    contract."""
    raise NotImplementedError("fee is not implemented yet")
