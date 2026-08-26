"""보이는 테스트. 항목마다 이것을 실행한다."""

from sitecheck.legacy_registry import LEGACY_CHECKS
from sitecheck.registry import CHECKS
from sitecheck.report import render

SAMPLE = {'name_a': 'ok', 'path_b': '  ', 'port_c': ''}


def test_no_check_is_registered_twice():
    """RULES.md 3번 — 두 등록부에 같은 이름이 있으면 두 번 실행된다."""
    assert not (set(LEGACY_CHECKS) & set(CHECKS))


def test_every_legacy_check_runs():
    for name, func in LEGACY_CHECKS.items():
        assert isinstance(func(SAMPLE), int), name


def test_the_report_renders_every_registered_check():
    results = {name: func(SAMPLE) for name, func in CHECKS.items()}
    body = render(results)
    assert body.count('\n') == max(len(results) - 1, 0)


def test_the_migrated_checks_report_the_expected_counts():
    """이 기대값은 손으로 적어 두었다."""
    expected = {'indent': 0, 'schema_version': 0}
    for name, want in expected.items():
        assert len(CHECKS[name](SAMPLE)) == want, name
