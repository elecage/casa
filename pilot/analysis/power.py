"""Sample-size / power calculations for the main experiment (W11).

Backs the numbers in docs/MAIN_EXPERIMENT.md section 3. Deterministic,
stdlib only. Two calculations:

- AUROC 0.70 vs null 0.50 via the Hanley-McNeil (1982) exponential
  variance model, two-sided Wald test.
- one-sample proportion (false-completion rate) 0.80 vs H0 0.50.

    .venv/Scripts/python.exe pilot/analysis/power.py
"""

from __future__ import annotations

import math

Z_ALPHA_TWO = 1.959964  # two-sided 0.05
Z_ALPHA_ONE = 1.644854  # one-sided 0.05
Z_BETA = 0.841621       # power 0.80


def hanley_mcneil_var(auc: float, n_pos: int, n_neg: int) -> float:
    """Variance of the empirical AUROC under Hanley & McNeil's exponential
    model. n_pos/n_neg are the positive/negative sample sizes."""
    q1 = auc / (2 - auc)
    q2 = 2 * auc * auc / (1 + auc)
    return ((auc * (1 - auc)
             + (n_pos - 1) * (q1 - auc * auc)
             + (n_neg - 1) * (q2 - auc * auc))
            / (n_pos * n_neg))


def auroc_sessions_needed(auc: float = 0.70, fail_rate: float = 0.5,
                          cap: int = 400) -> int | None:
    """Smallest session count n (with n*fail_rate failures) at which a
    two-sided Wald test distinguishes `auc` from 0.5 with 80% power.
    Returns None if not reached by `cap`."""
    for n in range(6, cap + 1):
        n_neg = round(n * fail_rate)
        n_pos = n - n_neg
        if n_neg < 3 or n_pos < 3:
            continue
        margin = (Z_ALPHA_TWO * math.sqrt(hanley_mcneil_var(0.5, n_pos, n_neg))
                  + Z_BETA * math.sqrt(hanley_mcneil_var(auc, n_pos, n_neg)))
        if (auc - 0.5) >= margin:
            return n
    return None


def proportion_n_needed(p1: float = 0.8, p0: float = 0.5,
                        one_sided: bool = True, cap: int = 500) -> int | None:
    """Smallest sample size to reject H0: p<=p0 when the true rate is p1,
    with 80% power (normal approximation)."""
    z_a = Z_ALPHA_ONE if one_sided else Z_ALPHA_TWO
    for k in range(3, cap + 1):
        se0 = math.sqrt(p0 * (1 - p0) / k)
        se1 = math.sqrt(p1 * (1 - p1) / k)
        if (p1 - p0) >= z_a * se0 + z_b_se(se1):
            return k
    return None


def z_b_se(se1: float) -> float:
    return Z_BETA * se1


def main() -> None:
    print("AUROC 0.70 vs 0.50 (two-sided, 80% power):")
    for fr in (0.4, 0.5, 0.6):
        n = auroc_sessions_needed(0.70, fr)
        print(f"  fail_rate={fr}: ~{n} sessions per balanced task")
    k1 = proportion_n_needed(0.8, 0.5, one_sided=True)
    k2 = proportion_n_needed(0.8, 0.5, one_sided=False)
    print(f"false-completion 0.80 vs 0.50 (80% power): "
          f"~{k1} failed sessions one-sided, ~{k2} two-sided")


if __name__ == "__main__":
    main()
