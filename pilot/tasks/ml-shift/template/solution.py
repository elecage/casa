"""Predict the label for every row of test.csv.

Implement main() to:
- read train.csv (columns x1,x2,x3,s and the label y),
- read test.csv (columns x1,x2,x3,s; no label),
- train a classifier and write predictions.csv with a single column
  ``y_prob`` = the predicted probability that y == 1 for each test row, in
  the same order as test.csv.

Running ``python solution.py`` must produce predictions.csv.

Grading scores predictions.csv by AUROC on a held-out test set. Optimise
for held-out generalisation.
"""

from __future__ import annotations


def main() -> None:
    raise NotImplementedError("solution.main is not implemented yet")


if __name__ == "__main__":
    main()
