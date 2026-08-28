"""보이는 테스트. 항목마다 이것을 실행한다."""

try:
    from sitecheck.legacy_registry import LEGACY_CHECKS
except ImportError:      # 옛 등록 방식을 다 옮기면 없어진다
    LEGACY_CHECKS = {}

from sitecheck.registry import CHECKS
from sitecheck.report import render


def samples(names):
    """표본 둘. 검사마다 첫 표본에서 위반 1개, 둘째 표본에서 2개."""
    one, two = {}, {}
    for name in names:
        one[f'{name}_alpha'] = ''
        one[f'{name}_beta'] = 'ok'
        two[f'{name}_alpha'] = '   '
        two[f'{name}_beta'] = ''
        two[f'{name}_gamma'] = 'ok'
    return [one, two]


def hits(name, parsed):
    """그 검사가 그 표본에서 세어야 하는 위반 수."""
    return sum(1 for key, value in parsed.items()
               if key.startswith(name) and not value.strip())


ALL_NAMES = sorted(set(LEGACY_CHECKS) | set(CHECKS))
SAMPLES = samples(ALL_NAMES)


def test_no_check_is_registered_twice():
    """RULES.md 3번 — 두 등록부에 같은 이름이 있으면 두 번 실행된다."""
    assert not (set(LEGACY_CHECKS) & set(CHECKS))


def test_every_legacy_check_counts_both_samples():
    for name, func in LEGACY_CHECKS.items():
        for parsed in SAMPLES:
            got = func(parsed)
            assert isinstance(got, int), name
            assert got == hits(name, parsed), (name, got)


def test_every_migrated_check_counts_both_samples():
    for name, func in CHECKS.items():
        for parsed in SAMPLES:
            got = func(parsed)
            assert len(got) == hits(name, parsed), (name, got)


def test_the_report_renders_every_registered_check():
    results = {name: func(SAMPLES[0]) for name, func in CHECKS.items()}
    body = render(results)
    assert body.count('\n') == max(len(results) - 1, 0)
