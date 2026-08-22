"""Subsystem A — input adapters. The spec is `docs/ingest.md`.

Every source has its own file format. An adapter's only job is to read that
format and hand back a list of `opsbox.record.Record`. No aggregation and no
sorting happens here.

**Account spelling differs per source.** The same account arrives with
different case and different surrounding whitespace depending on the source.
How to normalize it is the "Account spelling" section of `docs/ingest.md`.
"""

from __future__ import annotations

from pathlib import Path

from . import ac, bd, cj, df, eg, fh
from .accounts import normalize_account

#: The adapters that are attached. Register a new source here.
ADAPTERS = {
    "ac": ac,
    "bd": bd,
    "cj": cj,
    "df": df,
    "eg": eg,
    "fh": fh,
}


def read_all(data_dir: Path) -> list:
    """Read everything under `data/` that an attached adapter can read."""
    out = []
    for name, adapter in sorted(ADAPTERS.items()):
        for path in sorted(Path(data_dir).glob(adapter.PATTERN)):
            out.extend(adapter.read(path))
    return out
