"""Time windowing.

Records are grouped into fixed-size windows aligned to multiples of the
window size since the Unix epoch (see models.Window for the boundary
semantics).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .models import LogRecord, Window

_EPOCH = datetime(1970, 1, 1)


def _floor_align(ts: datetime, size_seconds: int) -> datetime:
    epoch = int((ts - _EPOCH).total_seconds())
    return _EPOCH + timedelta(seconds=epoch - epoch % size_seconds)


def build_windows(lo: datetime, hi: datetime, size_seconds: int) -> list[Window]:
    windows = []
    t = _floor_align(lo, size_seconds)
    step = timedelta(seconds=size_seconds)
    while t <= hi:
        windows.append(Window(start=t, end=t + step))
        t += step
    return windows


def _contains(window: Window, ts: datetime) -> bool:
    return window.start <= ts < window.end


def assign(records: list[LogRecord], size_seconds: int) -> list[tuple[Window, list[LogRecord]]]:
    if not records:
        return []
    lo = min(r.ts for r in records)
    hi = max(r.ts for r in records)
    windows = build_windows(lo, hi, size_seconds)
    buckets: dict[Window, list[LogRecord]] = {w: [] for w in windows}
    for record in records:
        for window in windows:
            if _contains(window, record.ts):
                buckets[window].append(record)
                break
    return [(w, buckets[w]) for w in windows]
