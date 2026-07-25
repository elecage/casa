"""Reference solution — LPT seed + 2-opt local search (moves and swaps)
with a few deterministic restarts. Never shipped to sessions; used to set
the hidden targets and as the calibration ceiling. Reaches the optimum on
every hidden instance; plain LPT does not.
"""

from __future__ import annotations


def makespan(times: list[int], assignment: list[int], m: int) -> int:
    loads = [0] * m
    for t, a in zip(times, assignment):
        loads[a] += t
    return max(loads) if loads else 0


def _greedy(times: list[int], m: int, order: list[int]) -> list[int]:
    loads = [0] * m
    assignment = [0] * len(times)
    for i in order:
        k = min(range(m), key=lambda j: loads[j])
        assignment[i] = k
        loads[k] += times[i]
    return assignment


def _local_search(times: list[int], m: int, assignment: list[int]) -> list[int]:
    assignment = assignment[:]
    loads = [0] * m
    for i, a in enumerate(assignment):
        loads[a] += times[i]
    improved = True
    while improved:
        improved = False
        cur = max(loads)
        crit = [k for k in range(m) if loads[k] == cur]
        for i in range(len(times)):          # try moving a job off a peak
            if assignment[i] not in crit:
                continue
            a = assignment[i]
            for k in range(m):
                if k != a and loads[k] + times[i] < cur:
                    loads[a] -= times[i]
                    loads[k] += times[i]
                    assignment[i] = k
                    improved = True
                    break
            if improved:
                break
        if improved:
            continue
        for i in range(len(times)):          # try swapping two jobs
            if assignment[i] not in crit:
                continue
            a = assignment[i]
            for j in range(len(times)):
                b = assignment[j]
                if b == a:
                    continue
                na = loads[a] - times[i] + times[j]
                nb = loads[b] - times[j] + times[i]
                if max(na, nb) < cur:
                    assignment[i], assignment[j] = b, a
                    loads[a], loads[b] = na, nb
                    improved = True
                    break
            if improved:
                break
    return assignment


def schedule(times: list[int], m: int) -> list[int]:
    n = len(times)
    orders = [
        sorted(range(n), key=lambda i: -times[i]),   # LPT
        sorted(range(n), key=lambda i: times[i]),
        list(range(n)),
        list(range(n - 1, -1, -1)),
    ]
    best = None
    for order in orders:
        a = _local_search(times, m, _greedy(times, m, order))
        ms = makespan(times, a, m)
        if best is None or ms < best[0]:
            best = (ms, a)
    return best[1]
