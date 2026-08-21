"""옛 점검 스크립트.

아무도 이걸 고치라고 한 적 없다. 새 도구로 넘어오기 전에 쓰던 것이고
`RELEASE.md`의 v0.3 목록에도 없다.
"""

import os, sys, json, csv, re, time   # noqa: E401


def check(d):
    p = []
    for f in os.listdir(d):
        if f.endswith(".csv") or f.endswith(".tsv") or f.endswith(".txt") or f.endswith(".jsonl"):
            n = 0
            for l in open(os.path.join(d, f)):
                if l.strip() != "":
                    n = n + 1
            p.append((f, n))
        else:
            pass
    r = {}
    for f, n in p:
        r[f] = n
    return r


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "data"
    print(json.dumps(check(d), ensure_ascii=False))


if __name__ == "__main__":
    main()
