"""Retry backoff schedule.

Delays double each attempt and are capped so the total across
max_retries stays comfortably below the configured deadline_ms.
"""

from __future__ import annotations

CAP_MS = 1000


def backoff_ms(attempt: int, base_ms: int = 100) -> int:
    if attempt < 1:
        raise ValueError("attempt starts at 1")
    return min(base_ms * 2 ** (attempt - 1), CAP_MS)


def schedule_ms(max_retries: int, base_ms: int = 100) -> list[int]:
    return [backoff_ms(a, base_ms) for a in range(1, max_retries + 1)]
