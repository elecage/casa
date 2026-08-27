"""보이는 테스트. 항목마다 이것을 실행한다."""

from sitecheck.legacy_registry import LEGACY_CHECKS
from sitecheck.registry import CHECKS
from sitecheck.report import render

#: 표본 둘. 같은 검사가 두 표본에서 다른 수를 내야 한다.
SAMPLES = [
    {'name_a': 'ok', 'path_b': '  ', 'port_c': ''},
    {'name_a': '', 'name_b': '   ', 'path_b': 'ok'},
]


def test_no_check_is_registered_twice():
    """RULES.md 3번 — 두 등록부에 같은 이름이 있으면 두 번 실행된다."""
    assert not (set(LEGACY_CHECKS) & set(CHECKS))


def test_every_legacy_check_counts_both_samples():
    for name, func in LEGACY_CHECKS.items():
        for parsed in SAMPLES:
            got = func(parsed)
            assert isinstance(got, int), name
            want = sum(1 for k, v in parsed.items()
                       if k.startswith(name) and not v.strip())
            assert got == want, (name, parsed)


def test_every_migrated_check_counts_both_samples():
    for name, func in CHECKS.items():
        for parsed in SAMPLES:
            got = func(parsed)
            want = sum(1 for k, v in parsed.items()
                       if k.startswith(name) and not v.strip())
            assert len(got) == want, (name, parsed)


def test_the_report_renders_every_registered_check():
    results = {name: func(SAMPLES[0]) for name, func in CHECKS.items()}
    body = render(results)
    assert body.count('\n') == max(len(results) - 1, 0)
