from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowConfig:
    """Aggregation settings. Windows are aligned to multiples of
    ``size_seconds`` since the Unix epoch."""

    size_seconds: int = 300
