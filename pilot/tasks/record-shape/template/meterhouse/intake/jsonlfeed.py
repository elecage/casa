"""JSONL feed adapter.

The newer sites push one JSON object per line. Same fields as the CSV feed;
see `docs/v03-metering.md`.
"""

from __future__ import annotations

from pathlib import Path

from ..record import Reading


def read_file(path: Path) -> tuple[list[Reading], list[str]]:
    """Return (readings, skipped) for one JSONL file."""
    raise NotImplementedError("jsonl feed is not wired up yet")
