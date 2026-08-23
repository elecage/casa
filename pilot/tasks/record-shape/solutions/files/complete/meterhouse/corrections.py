"""Corrections and as-of resolution (`docs/v04-corrections.md`).

A row with `corrects: X` replaces row X entirely. A chain applies in
`recorded_at` order and the last one wins. An as-of timestamp keeps only the
rows we had already learned about at that moment.
"""

from __future__ import annotations

from .record import Reading


def known_at(readings: list[Reading], as_of: str | None) -> list[Reading]:
    """Only the readings recorded at or before `as_of`."""
    if as_of is None:
        return list(readings)
    return [r for r in readings if r.recorded_at <= as_of]


def resolve(readings: list[Reading],
            as_of: str | None = None) -> tuple[list[Reading], list[str]]:
    """Return (effective readings, skipped).

    Effective readings are the ones that count: a superseded row drops out and
    the row that replaced it stands in its place. A row correcting an id we
    have never seen is skipped, not silently kept.
    """
    visible = known_at(readings, as_of)
    all_ids = {r.id for r in readings}
    kept: list[Reading] = []
    skipped: list[str] = []
    superseded = superseded_by(visible)
    for reading in visible:
        if reading.corrects and reading.corrects not in all_ids:
            skipped.append(f"{reading.source_file}:{reading.source_line}: "
                           "unknown correction target")
            continue
        if reading.id in superseded:
            continue
        kept.append(reading)
    return kept, skipped


def superseded_by(readings: list[Reading]) -> dict[str, str]:
    """Map an id to the id of the row that replaced it."""
    out: dict[str, str] = {}
    known = {r.id for r in readings}
    for reading in sorted(readings, key=lambda r: r.recorded_at):
        target = reading.corrects
        if target and target in known:
            out[target] = reading.id
    return out
