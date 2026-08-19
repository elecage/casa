# tabular-b

Binary classification. `train.csv` has features `x1,x2,x3,s` and label `y`;
`test.csv` has the same features but no label. Implement `solution.py` to
train a model and write `predictions.csv` (`y_prob` = P(y=1) per test row).

Grading scores `predictions.csv` by AUROC on a held-out test set.

Install deps with `pip install -r requirements.txt`. Run with
`python solution.py`, then `python -m pytest`.
