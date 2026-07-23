from __future__ import annotations

from xml.sax.saxutils import escape

from ..base import Exporter
from ..records import FIELD_ORDER
from ..registry import register


@register
class XmlExporter(Exporter):
    format_name = "xml"
    file_extension = ".xml"

    def render(self, records: list[dict]) -> str:
        lines = ["<records>"]
        for r in records:
            fields = "".join(f"<{k}>{escape(str(r[k]))}</{k}>" for k in FIELD_ORDER)
            lines.append(f"  <record>{fields}</record>")
        lines.append("</records>")
        return "\n".join(lines) + "\n"
