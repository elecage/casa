"""명령줄 진입점."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from . import VERSION, config, readers, reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="usagectl")
    parser.add_argument("--config", default="config.sample.json")
    parser.add_argument("--out", default="-", help="리포트를 쓸 파일. -면 표준 출력")
    parser.add_argument("--section", action="append", choices=sorted(reports.SECTIONS),
                        help="낼 절. 여러 번 줄 수 있다. 없으면 전부")
    parser.add_argument("--json", action="store_true", help="CSV 대신 JSON으로 낸다")
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def gather(settings: dict) -> list:
    records = readers.read_all(settings["source_dir"])
    return records[: settings["max_rows"]]


def main(argv: list[str] | None = None) -> int:
    # 리포트에 한글 절 제목이 들어가므로 콘솔 코드페이지와 무관하게 UTF-8로 낸다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    args = build_parser().parse_args(argv)
    settings = config.load(args.config)
    records = gather(settings)

    names = args.section or sorted(reports.SECTIONS)
    rows: list[list[str]] = []
    for name in names:
        section = reports.SECTIONS[name]
        rows.append([section.TITLE])
        rows.extend(section.render(records))

    handle = sys.stdout if args.out == "-" else Path(args.out).open(
        "w", encoding="utf-8", newline="")
    try:
        csv.writer(handle, lineterminator="\n").writerows(rows)
    finally:
        if handle is not sys.stdout:
            handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
