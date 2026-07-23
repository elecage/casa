from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    """Position and velocity in the orbital plane."""

    r: tuple[float, float]
    v: tuple[float, float]
