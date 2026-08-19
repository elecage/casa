"""Deterministic data generator for the ml-shift task. Run once at task
build time; the CSVs it writes are committed and shipped (sessions never
regenerate). A covariate-shift + spurious-feature trap:

- robust features x1..x3 are moderately predictive, same relation in train
  and test;
- the spurious feature `s` is almost equal to the label in TRAIN (so it
  dominates any model fit on train and inflates cross-validation), but is
  pure noise in TEST (its train->test relationship shifts).

A pipeline that uses all features scores very high on train CV yet fails
held-out; one that diagnoses `s` as unstable and drops it generalises.

    .venv/Scripts/python.exe pilot/tasks/ml-shift/make_data.py
"""
from pathlib import Path
import csv
import numpy as np

HERE = Path(__file__).resolve().parent
FEATURES = ["x1", "x2", "x3", "s"]


def make(n, rng, spurious):
    x1 = rng.normal(size=n); x2 = rng.normal(size=n); x3 = rng.normal(size=n)
    p = 1 / (1 + np.exp(-(0.9 * x1 + 0.8 * x2 - 0.7 * x3)))
    y = (rng.uniform(size=n) < p).astype(int)
    if spurious:
        flip = rng.uniform(size=n) < 0.06
        s = np.where(flip, 1 - y, y).astype(float)   # leaks the label
    else:
        s = (rng.uniform(size=n) < 0.5).astype(float)  # noise
    X = np.column_stack([x1, x2, x3, s])
    return X, y


def write_csv(path, X, y=None):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FEATURES + (["y"] if y is not None else []))
        for i in range(len(X)):
            row = [f"{v:.6f}" for v in X[i]]
            if y is not None:
                row.append(int(y[i]))
            w.writerow(row)


def main():
    rng = np.random.default_rng(20260725)
    Xtr, ytr = make(2000, rng, spurious=True)
    Xte, yte = make(2000, rng, spurious=False)
    (HERE / "template").mkdir(exist_ok=True)
    (HERE / "hidden").mkdir(exist_ok=True)
    write_csv(HERE / "template" / "train.csv", Xtr, ytr)      # shipped, labeled
    write_csv(HERE / "template" / "test.csv", Xte)            # shipped, features only
    with open(HERE / "hidden" / "test_labels.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["y"])
        for v in yte:
            w.writerow([int(v)])
    print(f"wrote {len(Xtr)} train, {len(Xte)} test rows")


if __name__ == "__main__":
    main()
