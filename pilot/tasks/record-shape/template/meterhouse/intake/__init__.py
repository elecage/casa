"""Feed adapters. One module per source format."""

from __future__ import annotations

from pathlib import Path

from ..record import Reading
from . import csvfeed, jsonlfeed


def read_dir(directory: Path) -> tuple[list[Reading], list[str]]:
    """Read every feed file in `directory`.

    Returns (readings, skipped). `skipped` lines are reported by the CLI so
    the operator can go and fix the source.
    """
    readings: list[Reading] = []
    skipped: list[str] = []
    for path in sorted(Path(directory).iterdir()):
        if path.suffix == ".csv":
            got, bad = csvfeed.read_file(path)
        elif path.suffix == ".jsonl":
            got, bad = jsonlfeed.read_file(path)
        else:
            continue
        readings.extend(got)
        skipped.extend(bad)
    return readings, skipped
