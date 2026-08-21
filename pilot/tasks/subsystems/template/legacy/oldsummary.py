"""옛 요약기. 다른 팀이 아직 쓴다 — 건드리지 않는다.

새 리포트로 넘어가기 전에 쓰던 것이다. 여기 손대지 말고 `opsbox/report/`를
쓴다.
"""

import sys, os, json, csv, io   # noqa: E401  (옛 코드 그대로 둔다)


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
