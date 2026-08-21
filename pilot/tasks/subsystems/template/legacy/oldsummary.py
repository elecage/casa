"""The old summarizer. Another team still uses it — do not touch it.

This is what was used before the move to the new report. Leave it alone and
use `opsbox/report/` instead.
"""

import sys, os, json, csv, io   # noqa: E401  (left as the old code had it)


def summarize(rows):
    t = 0
    d = {}
    for r in rows:
        if r.get("status") != "void":
            t = t + int(r["units"])
            a = r["account"]
            if a in d:
                d[a] = d[a] + int(r["units"])
            else:
                d[a] = int(r["units"])
    return {"t": t, "d": d}


def main():
    print(json.dumps(summarize([])))
