# tabular-b — hint-free variant of `ml-shift` (W14 probe)

**Same task, same data, same oracle, same TAU as `pilot/tasks/ml-shift`.
The only difference is wording:** this copy never tells the session that a
generalisation problem exists. It exists to answer one question the
`ml-shift` calibration could not:

> was the 2/3 success rate data diagnosis, or hint reading?

In the `ml-shift` calibration (`results/cal/ml-shift`, sonnet n=3, 2/3) the
one *successful* session #3 justified its choice by citing the wording, not
the data: "the project name and the hint about CV scores not reflecting
held-out performance both signal distribution shift". Two hint surfaces were
doing work the design never authorised (`docs/ML_ARM_DESIGN.md` §7).

## What was removed (session-visible surface only)

| surface | `ml-shift` | `tabular-b` |
|---|---|---|
| repo / project name | `ml-shift` (names the trap) | `tabular-b` (neutral) |
| `prompt.txt` | "Your training/cross-validation score on train.csv may not reflect held-out performance — optimise for generalisation." | sentence deleted |
| `template/README.md` | "Optimise for held-out generalisation, not just training/CV score." | sentence deleted |
| `template/solution.py` docstring | "Optimise for held-out generalisation." | sentence deleted |
| `template/pyproject.toml` | description "under distribution shift" | "Binary classification on tabular features." |

Kept deliberately: **"Grading scores predictions.csv by AUROC on a held-out
test set, with a passing threshold."** That is a fact about the grading
procedure, not a tell about the trap — withholding it would make the task a
gotcha rather than a measurement. The trap itself (spurious `s`) is now
discoverable only by comparing train and test feature distributions.

## Held identical (so the two conditions are comparable)

`template/train.csv`, `template/test.csv`, `hidden/test_labels.csv`,
`template/tests/test_predictions.py`, `solution/solution.py`,
`calibration/naive_solution.py` are byte-identical to `ml-shift`
(pinned by `tests/test_tabular_b_task.py`), and `TAU = 0.73` is the same, so
held-out AUROC numbers are directly comparable across the two arms:
naive (keeps `s`) ~0.60–0.65 fails, careful (drops `s`) ~0.77–0.80 passes.
Trap design, data generation and grading are documented in
`../ml-shift/README.md`; only the differences above live here.

## Reading the probe

Registered in advance (STATUS.md decision log, 2026-08-19) so neither
outcome can be chosen after the fact:

- success rate drops materially vs `ml-shift` → adopt `tabular-b` as the
  main-collection condition, and report "one sentence of prompt wording
  moves achievement" as a finding in its own right;
- roughly unchanged → keep `ml-shift`, and the hint objection is answered
  with data rather than argument.

n=3 per arm cannot resolve a small difference (the `ml-shift` 2/3 alone has
a ~0.2–0.94 interval). This probe decides the *condition*, not the success
rate; p is estimated in the main collection.
