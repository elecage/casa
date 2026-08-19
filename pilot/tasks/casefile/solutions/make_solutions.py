#!/usr/bin/env python3
"""Generate the three reference variants from `_impl.py`.

Run: python pilot/tasks/casefile/solutions/make_solutions.py

The variants differ only in the CONVENTIONS block, which is the whole point:
A and B are equally valid readings of the conflicting documents, `mixed`
applies the same choices inconsistently. If the grader is right, A and B both
score full marks and `mixed` loses only consistency points.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
START = "# --- CONVENTIONS ---"
END = "# --- end CONVENTIONS ---"

VARIANTS = {
    # UTC timestamps, source-prefixed ids, missing note as ""
    "a": {
        "TIME_UTC": "True", "ID_PREFIXED": "True", "MISSING_NOTE": '""',
        "ID_FIELD": '"record_id"', "ID_PREFIXED_FIXED": "True",
    },
    # explicit offsets, plain ids, missing note as null
    "b": {
        "TIME_UTC": "False", "ID_PREFIXED": "False", "MISSING_NOTE": "None",
        "ID_FIELD": '"case_id"', "ID_PREFIXED_FIXED": "False",
    },
    # same decisions, applied inconsistently: fixed-width rows get prefixed ids
    # while csv rows do not. Every milestone still works.
    "mixed": {
        "TIME_UTC": "True", "ID_PREFIXED": "False", "MISSING_NOTE": '""',
        "ID_FIELD": '"record_id"', "ID_PREFIXED_FIXED": "True",
    },
}


def render(values: dict[str, str]) -> str:
    source = (HERE / "_impl.py").read_text(encoding="utf-8")
    head, rest = source.split(START, 1)
    _, tail = rest.split(END, 1)
    block = [START + "-" * 55]
    for name, value in values.items():
        block.append(f"{name} = {value}")
    block.append(END + "-" * 51)
    return head + "\n".join(block) + tail


def main() -> int:
    for name, values in VARIANTS.items():
        target = HERE / f"casefile_{name}.py"
        target.write_text(render(values), encoding="utf-8", newline="\n")
        print(f"wrote {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
