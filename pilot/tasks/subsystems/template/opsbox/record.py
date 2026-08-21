"""The common record the subsystems pass around.

The six subsystems each deal with their own file format, but once something is
inside it all looks like this. Attaching a new source or a new report goes
through here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Record:
    source: str         # which source it came from
    account: str        # who used it; spelled differently per source
    at: datetime        # record timestamp, read as local time by `parse_ts`
    units: int          # billed quantity
    status: str = "ok"  # ok | adjusted | void
    at_raw: str = ""    # the timestamp string exactly as the source wrote it

    # Why `at_raw` is carried around: `parse_ts` drops the zone offset before
    # reading, so `at` alone cannot tell you which zone the record came from.
    # Whether the month boundary is taken in UTC or in local time is decided by
    # the aggregation side (subsystem B), and without the original string that
    # choice does not exist at all.


def is_billable(record: Record) -> bool:
    """Does this record go into the totals?

    Only ``void`` is left out. ``adjusted`` was corrected after the fact and
    still counts.
    """
    return record.status != "void"
