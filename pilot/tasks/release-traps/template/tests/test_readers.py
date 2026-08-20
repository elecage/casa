from pathlib import Path

from usagectl import readers
from usagectl.readers import alpha, beta, gamma

DATA = Path(__file__).resolve().parents[1] / "data"


def test_alpha_reads_every_row():
    records = alpha.read(DATA / "alpha-2026-07.csv")
    assert len(records) == 5
    assert records[0].account == "acct-001"
    assert records[0].units == 120


def test_alpha_keeps_status():
    statuses = {r.status for r in alpha.read(DATA / "alpha-2026-07.csv")}
    assert statuses == {"ok", "adjusted", "void"}


def test_beta_reads_fixed_width_columns():
    records = beta.read(DATA / "beta-2026-07.txt")
    assert records[0].account == "acct-004"
    assert records[0].units == 60


def test_beta_parses_slash_dates():
    records = beta.read(DATA / "beta-2026-07.txt")
    assert records[0].at.month == 7


def test_gamma_reads_json_lines():
    records = gamma.read(DATA / "gamma-2026-07.jsonl")
    assert all(r.source == "gamma" for r in records)
    assert {r.account for r in records} <= {"acct-003", "acct-005"}


def test_registry_maps_names_to_modules():
    for name, module in readers.REGISTRY.items():
        assert hasattr(module, "read") and hasattr(module, "PATTERN")
        assert name in module.PATTERN


def test_read_all_uses_the_registry():
    sources = {r.source for r in readers.read_all(DATA)}
    assert sources == set(readers.REGISTRY)
