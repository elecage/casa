"""Command line: jobq [--deadline-ms N] [--batch-size N] ...

Flags mirror setting keys and win over both defaults.ini and JOBQ_* env
overrides.
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobq")
    parser.add_argument("--deadline-ms", dest="deadline_ms", type=int)
    parser.add_argument("--max-retries", dest="max_retries", type=int)
    parser.add_argument("--batch-size", dest="batch_size", type=int)
    parser.add_argument("--queue-name", dest="queue_name")
    return parser


def cli_overrides(argv: list[str]) -> dict:
    args = build_parser().parse_args(argv)
    return {k: v for k, v in vars(args).items() if v is not None}
