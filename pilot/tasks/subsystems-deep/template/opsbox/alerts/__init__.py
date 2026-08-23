"""Subsystem C — alert rules. The spec is `docs/alerts.md`.

Puts a per-account threshold on top of what the aggregation (subsystem B)
produced and raises an alert for everything over it.

**It has to use the month boundary B decided.** Right now it works one out on
its own and that basis differs from B's — see the header of `evaluate.py` and
the "Month boundary" section of `docs/alerts.md`.
"""

from __future__ import annotations

from . import evaluate, rules
from .evaluate import fire, last_seen, monthly_totals
from .rules import load
