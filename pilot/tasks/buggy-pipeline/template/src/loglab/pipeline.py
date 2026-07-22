"""End-to-end pipeline: files in, report dict out."""

from __future__ import annotations

from pathlib import Path

from . import aggregate, loader, parser, report, windowing
from .config import WindowConfig


def run(paths: list[str | Path], config: WindowConfig | None = None) -> dict:
    config = config or WindowConfig()
    rows: list[dict[str, str]] = []
    for path in paths:
        rows.extend(loader.load(path))
    records = parser.parse_rows(rows)
    assigned = windowing.assign(records, config.size_seconds)
    stats = aggregate.summarize(assigned)
    return report.build(stats)
