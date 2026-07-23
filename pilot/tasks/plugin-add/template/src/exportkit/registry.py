"""Format registry.

Exporter classes self-register via the @register decorator, keyed by
their ``format_name``. Registration is an import-time side effect: a
format exists once its module has been imported (see exporters/__init__).
"""

from __future__ import annotations

from .base import Exporter
from .errors import ExportError

_REGISTRY: dict[str, Exporter] = {}


def register(cls: type[Exporter]) -> type[Exporter]:
    if not (isinstance(cls, type) and issubclass(cls, Exporter)):
        raise TypeError("@register expects an Exporter subclass")
    if not cls.format_name:
        raise ValueError("Exporter needs a non-empty format_name")
    _REGISTRY[cls.format_name] = cls()
    return cls


def get(name: str) -> Exporter:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ExportError(f"unknown format: {name}") from None


def available() -> list[str]:
    return sorted(_REGISTRY)
