"""The old check script.

Nobody asked for this to be fixed. It is what was used before the move to the
new tool, and it is not in the v0.3 list in `RELEASE.md`.
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
