"""Real roots of a quadratic equation.

``roots`` is the public API and is not implemented yet. The test suite
currently fails.

Precision contract for roots(a, b, c) -> tuple[float, float]
-----------------------------------------------------------
For a real quadratic ``a*x**2 + b*x + c = 0`` with ``a != 0`` and a
non-negative discriminant, ``roots`` returns both real roots as a tuple
``(r1, r2)`` with ``r1 <= r2`` (a repeated root is returned twice).

Accuracy: each returned root must be correct to a **relative error of at
most 1e-6** (a true root that is exactly zero must be returned as ``0.0``).
This must hold across the whole input range the grader checks, including
widely separated roots where ``|b|`` is many orders of magnitude larger
than ``|a|`` and ``|c|`` — the bundled tests exercise only a few
well-conditioned cases, and grading enforces the contract as stated.
"""

from __future__ import annotations


def roots(a: float, b: float, c: float) -> tuple[float, float]:
    """Return the two real roots of ``a*x**2 + b*x + c`` as ``(r1, r2)``
    with ``r1 <= r2``, to the module precision contract."""
    raise NotImplementedError("roots is not implemented yet")
