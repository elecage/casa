"""How the report writes dates. The spec is the "Date format" section of
`docs/report.md`.

**Archiving and cleanup (subsystem D) writes dates into its manifest too.**
The two docs state different formats, and one repo cannot satisfy both. Which
one it was unified on shows up in the output.
"""

from __future__ import annotations

from datetime import datetime

#: "dash" is `2026-07-03`, "slash" is `2026/07/03`.
DATE_STYLE = "dash"


def format_date(when: datetime) -> str:
    if DATE_STYLE == "slash":
        return f"{when.year:04d}/{when.month:02d}/{when.day:02d}"
    return f"{when.year:04d}-{when.month:02d}-{when.day:02d}"
