from __future__ import annotations

import json

from ..base import Exporter
from ..records import FIELD_ORDER
from ..registry import register


@register
class JsonExporter(Exporter):
    format_name = "json"
    file_extension = ".json"

    def render(self, records: list[dict]) -> str:
        ordered = [{k: r[k] for k in FIELD_ORDER} for r in records]
        return json.dumps(ordered, indent=2) + "\n"
