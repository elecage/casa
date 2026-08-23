"""Subsystem E — export. The spec is `docs/export.md`.

Puts the report into a shape the outside can read. **It does not lean on any
other subsystem's decision** — it copies out the report it was handed.
"""

from __future__ import annotations

from . import flat, pdf
from .flat import COLUMNS, to_csv
