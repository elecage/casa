"""Reference solution (careful). Never shipped. Diagnoses that feature `s`
is unstable between train and test (in train it nearly equals the label; in
test it is noise) and drops it, training only on the robust features
x1..x3. Reaches held-out AUROC ~0.80, clearing the target; a pipeline that
keeps `s` overfits to the leak and fails held-out.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).resolve().parent
ROBUST = ["x1", "x2", "x3"]        # `s` deliberately excluded


def _load(path, cols, with_y):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    X = np.array([[float(r[c]) for c in cols] for r in rows])
    y = np.array([int(r["y"]) for r in rows]) if with_y else None
    return X, y


def main() -> None:
    Xtr, ytr = _load(HERE / "train.csv", ROBUST, True)
    Xte, _ = _load(HERE / "test.csv", ROBUST, False)
    model = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
    prob = model.predict_proba(Xte)[:, 1]
    with open(HERE / "predictions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["y_prob"])
        for p in prob:
            w.writerow([f"{p:.6f}"])


if __name__ == "__main__":
    main()
