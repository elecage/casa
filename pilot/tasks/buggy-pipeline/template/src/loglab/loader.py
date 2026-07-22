"""CSV loading. Produces raw string dicts; no interpretation happens here."""

from __future__ import annotations

import csv
from pathlib import Path


REQUIRED_COLUMNS = {"timestamp", "path", "status", "bytes"}


def load(path: str | Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    if rows and not REQUIRED_COLUMNS.issubset(rows[0].keys()):
        missing = REQUIRED_COLUMNS - set(rows[0].keys())
        raise ValueError(f"missing columns: {sorted(missing)}")
    return rows
