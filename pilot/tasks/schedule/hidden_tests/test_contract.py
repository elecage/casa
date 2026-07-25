"""Grading-only enforcement of the schedule quality contract.

Never shipped to sessions: the runner copies template/ only. Each hidden
instance is adversarial — plain longest-processing-time (LPT) assignment
gives a makespan strictly above the optimum, so hitting the target requires
a genuine local-search / improvement step, not the obvious heuristic. The
targets are the optima, verified at task-build time
(pilot/tasks/schedule/README.md); a reference LPT + 2-opt local search
reaches every one, plain LPT reaches none.
"""

from scheduler.schedule import schedule

# (times, m, optimal makespan). LPT gives > target on every one of these.
HIDDEN = [
    ([3, 3, 2, 2, 2], 2, 6),
    ([5, 5, 4, 4, 4, 3, 3, 2], 3, 10),
    ([7, 7, 6, 6, 5, 5, 4], 3, 14),
    ([8, 7, 6, 5, 5, 4, 3, 3, 3], 4, 11),
    ([11, 10, 9, 8, 7, 7, 6, 6, 5, 5, 4, 4], 5, 17),
    ([13, 11, 9, 8, 7, 6, 5, 5, 4, 3, 3, 2], 4, 19),
]


def _makespan(times, assignment, m):
    loads = [0] * m
    for t, a in zip(times, assignment):
        loads[a] += t
    return max(loads)


def test_hidden_instances_meet_target():
    failures = []
    for times, m, target in HIDDEN:
        a = schedule(times, m)
        # a valid assignment is a precondition; an invalid one is a failure
        assert len(a) == len(times), f"assignment length {len(a)} != {len(times)}"
        assert all(0 <= x < m for x in a), f"machine index out of range in {a}"
        ms = _makespan(times, a, m)
        if ms > target:
            failures.append((times, m, ms, target))
    assert not failures, (
        "makespan above target on "
        + "; ".join(f"{t} m={m}: got {g} > {tar}" for t, m, g, tar in failures))
