"""Tests for the claim-gap analysis.

The conclusion drawn from this script was a *negative* one, so the property
that matters most is that a flat signal reads as 0.5 rather than as evidence.
Several signals turned out to be near-constant on real data; if ties were
scored as wins those would have looked informative and the conclusion would
have flipped.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pilot" / "analysis"))

import claim_gap  # noqa: E402


def test_constant_signal_scores_exactly_chance():
    """Ties count as half — otherwise a flat signal looks like a finding."""
    values = [1.0] * 6
    labels = [True, True, False, False, True, False]
    assert claim_gap.auroc(values, labels) == 0.5


def test_perfect_and_inverted_separation():
    labels = [True, True, False, False]
    assert claim_gap.auroc([1.0, 1.0, 0.0, 0.0], labels) == 1.0
    assert claim_gap.auroc([0.0, 0.0, 1.0, 1.0], labels) == 0.0


def test_auroc_is_none_without_both_classes():
    assert claim_gap.auroc([1.0, 2.0], [True, True]) is None
    assert claim_gap.auroc([1.0, 2.0], [False, False]) is None


def test_primary_signals_are_the_externally_evidenced_ones():
    """Which signals were pre-registered as primary must not drift quietly."""
    assert set(claim_gap.PRIMARY) == {"단언어휘밀도", "읽기편중"}
    assert set(claim_gap.PRIMARY) <= set(claim_gap.SIGNALS)
