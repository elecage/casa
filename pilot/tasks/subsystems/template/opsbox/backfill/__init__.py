"""Subsystem F — backfill. The spec is `docs/backfill.md`.

Compares the monthly numbers that already went out (`published/`) with the
numbers recounted from the current samples and records the difference. The
files that shipped are not corrected.

**It leans on two things.** Account names have to use the rule the input
adapters (A) decided, and the month boundary has to use the basis the
aggregation (B) decided. Right now both are worked out here separately.
"""

from __future__ import annotations

from . import plan
from .plan import delta, published, recomputed
