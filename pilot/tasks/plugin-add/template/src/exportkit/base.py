"""Exporter contract.

Subclasses set ``format_name`` / ``file_extension`` and implement
``render()``. They must NOT override ``export()``: validation happens
there, before any rendering, so every format rejects bad input the same
way (ExportError — see records.check_records).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .records import check_records


class Exporter(ABC):
    format_name: str = ""
    file_extension: str = ""

    def export(self, records: list[dict]) -> str:
        check_records(records)
        return self.render(records)

    @abstractmethod
    def render(self, records: list[dict]) -> str:
        """Return the serialized text; input is already validated."""
