from __future__ import annotations

from ..base import Exporter
from ..records import FIELD_ORDER
from ..registry import register


@register
class YamlExporter(Exporter):
    format_name = "yaml"
    file_extension = ".yaml"

    def render(self, records: list[dict]) -> str:
        lines = []
        for r in records:
            first, *rest = FIELD_ORDER
            lines.append(f"- {first}: {r[first]}")
            lines.extend(f"  {k}: {r[k]}" for k in rest)
        return "\n".join(lines) + "\n"
