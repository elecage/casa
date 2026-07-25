"""Naive solution — trains on ALL features including the spurious `s`.
Never shipped. Gets a great train/CV score (s nearly equals the label in
train) but fails held-out (s is noise in test): the textbook shortcut-
learning failure. Drop-in as solution.py to confirm the hidden oracle
separates the naive pipeline from a careful, shift-aware one.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).resolve().parent
ALL = ["x1", "x2", "x3", "s"]      # keeps the spurious feature


def _load(path, cols, with_y):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    X = np.array([[float(r[c]) for c in cols] for r in rows])
    y = np.array([int(r["y"]) for r in rows]) if with_y else None
    return X, y


def main() -> None:
    Xtr, ytr = _load(HERE / "train.csv", ALL, True)
    Xte, _ = _load(HERE / "test.csv", ALL, False)
    model = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
    prob = model.predict_proba(Xte)[:, 1]
    with open(HERE / "predictions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["y_prob"])
        for p in prob:
            w.writerow([f"{p:.6f}"])


if __name__ == "__main__":
    main()
