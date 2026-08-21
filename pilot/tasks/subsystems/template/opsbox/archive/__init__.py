"""Subsystem D — archiving and cleanup. The spec is `docs/archive.md`.

Picks what is old or large and builds an archive manifest.

**It has to use the account spelling rule the input adapters (subsystem A)
decided.** Right now `select.py` keeps a rule of its own, so the names on the
two sides disagree.
"""

from __future__ import annotations

from . import manifest, select
from .manifest import render
from .select import by_age, by_size, older_than
