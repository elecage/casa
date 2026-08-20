import json
from pathlib import Path

from usagectl import VERSION, config
from usagectl.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_a_three_part_string():
    assert VERSION.count(".") == 2


def test_parser_accepts_json_flag():
    args = build_parser().parse_args(["--json"])
    assert args.json is True


def test_config_falls_back_to_defaults(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({}), encoding="utf-8")
    settings = config.load(path)
    assert settings["source_dir"] == config.DEFAULT_SOURCE_DIR
    assert settings["max_rows"] == config.DEFAULT_MAX_ROWS


def test_main_writes_a_report(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    out = tmp_path / "report.csv"
    assert main(["--config", "config.sample.json", "--out", str(out)]) == 0
    assert "acct-001" in out.read_text(encoding="utf-8")
