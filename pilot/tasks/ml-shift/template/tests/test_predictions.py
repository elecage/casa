"""Visible checks — validity of predictions.csv only (no held-out labels
are available here). These pass once solution.py has been run and produced
a well-formed predictions.csv. Do not modify.
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TEST = HERE / "test.csv"
PRED = HERE / "predictions.csv"


def _n_test_rows():
    return sum(1 for _ in open(TEST, encoding="utf-8")) - 1


def test_predictions_exist_and_valid():
    assert PRED.exists(), "run `python solution.py` to produce predictions.csv"
    rows = list(csv.DictReader(open(PRED, encoding="utf-8")))
    assert len(rows) == _n_test_rows(), "one prediction per test row required"
    probs = [float(r["y_prob"]) for r in rows]
    assert all(0.0 <= p <= 1.0 for p in probs), "y_prob must be in [0, 1]"
    assert len(set(probs)) > 1, "predictions must not be constant"
