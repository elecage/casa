"""Tests for the session-independence order-effect checks
(pilot/analysis/session_independence.py)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "session_independence", ROOT / "pilot" / "analysis" / "session_independence.py")
si = importlib.util.module_from_spec(spec)
spec.loader.exec_module(si)


def test_success_by_bins_flat_no_trend():
    # alternating success -> each third ~50%, no monotone rise
    items = [(i, i % 2 == 0) for i in range(1, 13)]
    bins = si.success_by_bins(items, bins=3)
    assert len(bins) == 3
    assert all(tot == 4 for _, tot in bins)
    fracs = [s / tot for s, tot in bins]
    assert fracs == [0.5, 0.5, 0.5]


def test_success_by_bins_detects_convergence():
    # failures early, successes late -> rising fraction (would flag leakage)
    items = [(i, i > 6) for i in range(1, 13)]
    fracs = [s / tot for s, tot in si.success_by_bins(items, bins=3)]
    assert fracs[0] < fracs[-1]
    assert fracs[0] == 0.0 and fracs[-1] == 1.0


def test_success_by_bins_uses_index_order_not_file_order():
    # unsorted input; late indices succeed
    items = [(9, True), (1, False), (5, False), (12, True), (3, False), (7, True)]
    bins = si.success_by_bins(items, bins=3)
    # sorted indices: 1F 3F 5F 7T 9T 12T -> [0/2, ?, 2/2]
    assert bins[0][0] == 0
    assert bins[-1][0] == 2


def test_similarity_by_distance_adjacent_vs_distant():
    # sessions 1 and 2 identical; far-apart sessions differ -> adjacent higher
    seqs = {
        1: ["Read", "Edit", "Bash"],
        2: ["Read", "Edit", "Bash"],
        12: ["Grep", "Grep", "Write"],
    }
    out = si.similarity_by_distance(seqs, near=1, far=10)
    assert out["adjacent_n"] == 1 and out["distant_n"] >= 1
    assert out["adjacent_mean"] == 1.0
    assert out["distant_mean"] < out["adjacent_mean"]
    assert out["delta"] > 0


def test_similarity_by_distance_empty_when_no_pairs():
    out = si.similarity_by_distance({1: ["Read"]}, near=1, far=10)
    assert out["adjacent_mean"] is None and out["distant_mean"] is None
    assert out["delta"] is None
