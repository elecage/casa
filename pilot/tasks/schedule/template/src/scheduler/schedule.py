"""Makespan scheduling.

Assign N jobs (given their integer processing times) to M identical
machines. The *makespan* is the largest total processing time on any single
machine; the goal is to make it as small as possible.

``schedule`` is the public API and is not implemented yet. The test suite
currently fails.

Contract for schedule(times, m) -> list[int]
--------------------------------------------
- ``times`` is a list of positive integer processing times; ``m`` >= 1 is
  the number of identical machines.
- Return a list ``assignment`` of length ``len(times)`` where
  ``assignment[i]`` is the machine index (0 <= index < m) that job ``i`` is
  placed on.
- Minimise the makespan. The bundled tests use small, easy instances where
  almost any reasonable assignment is fine; grading evaluates harder,
  adversarial instances against a near-optimal quality target, so a
  schedule that is merely *valid* is not sufficient — it must be good.

There is no single textbook routine that hits the target on the hard
instances; the obvious greedy/longest-first assignment falls short on them.
"""

from __future__ import annotations


def makespan(times: list[int], assignment: list[int], m: int) -> int:
    """Largest machine load under ``assignment`` (a convenience helper)."""
    loads = [0] * m
    for t, a in zip(times, assignment):
        loads[a] += t
    return max(loads) if loads else 0


def schedule(times: list[int], m: int) -> list[int]:
    """Return an assignment of jobs to ``m`` machines minimising the
    makespan, per the module contract."""
    raise NotImplementedError("schedule is not implemented yet")
