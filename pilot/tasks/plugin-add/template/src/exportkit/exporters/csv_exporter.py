from __future__ import annotations

import csv
import io

from ..base import Exporter
from ..records import FIELD_ORDER
from ..registry import register


@register
class CsvExporter(Exporter):
    format_name = "csv"
    file_extension = ".csv"

    def render(self, records: list[dict]) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=FIELD_ORDER,
                                extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
        return buf.getvalue()
