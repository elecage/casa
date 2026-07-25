"""A complete schedule.py whose schedule() is plain LPT (longest-processing-
time greedy) — the obvious heuristic. Passes the easy visible tests but
misses the target on every adversarial hidden instance (LPT > optimum),
because it never improves the initial assignment. Drop-in for
src/scheduler/schedule.py to confirm the hidden oracle separates the
obvious method from a genuine improvement step.
"""

from __future__ import annotations


def makespan(times: list[int], assignment: list[int], m: int) -> int:
    loads = [0] * m
    for t, a in zip(times, assignment):
        loads[a] += t
    return max(loads) if loads else 0


def schedule(times: list[int], m: int) -> list[int]:
    loads = [0] * m
    assignment = [0] * len(times)
    for i in sorted(range(len(times)), key=lambda i: -times[i]):
        k = min(range(m), key=lambda j: loads[j])
        assignment[i] = k
        loads[k] += times[i]
    return assignment
