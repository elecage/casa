"""Core value objects.

All timestamps in loglab are naive datetimes that represent UTC wall-clock
time. The parser is responsible for normalizing every input timestamp to
this convention before records enter the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LogRecord:
    ts: datetime          # naive, UTC
    path: str
    status: int
    bytes_sent: int


@dataclass(frozen=True)
class Window:
    start: datetime       # inclusive
    end: datetime         # exclusive


@dataclass(frozen=True)
class WindowStats:
    start: datetime
    end: datetime
    count: int
    errors: int
    bytes_total: int
