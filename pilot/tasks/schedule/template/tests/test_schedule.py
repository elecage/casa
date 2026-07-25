"""Visible checks for schedule — small, easy instances only.

These fail until schedule is implemented. They deliberately avoid the hard,
adversarial instances that grading uses. Do not modify.
"""

from scheduler.schedule import makespan, schedule


def _valid(times, m, assignment):
    assert len(assignment) == len(times)
    assert all(0 <= a < m for a in assignment)


def test_even_small_two_machines():
    times, m = [4, 4, 4, 4], 2
    a = schedule(times, m)
    _valid(times, m, a)
    assert makespan(times, a, m) <= 8            # optimal, trivially reached


def test_even_small_three_machines():
    times, m = [2, 2, 2, 2, 2, 2], 3
    a = schedule(times, m)
    _valid(times, m, a)
    assert makespan(times, a, m) <= 4


def test_uniform_three_machines():
    times, m = [5, 5, 5, 5, 5, 5], 3
    a = schedule(times, m)
    _valid(times, m, a)
    assert makespan(times, a, m) <= 10
