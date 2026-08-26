"""여러 검사가 함께 쓰는 코드."""

from __future__ import annotations


def normalise_location(raw: str) -> str:
    """경로 표기를 하나로 맞춘다. 슬래시와 끝의 구분자를 정리한다."""
    return raw.replace("\\", "/").rstrip("/").strip()


def within_window(value: int, start: int, end: int) -> bool:
    """구간 안인가. **끝값을 포함하지 않는다.**"""
    return start <= value < end


def normalise_result(result) -> list[dict]:
    """검사가 돌려준 것을 보고 계층이 쓰는 모양으로 맞춘다.

    건수를 돌려주는 검사와 목록을 돌려주는 검사를 둘 다 받는다.
    """
    if isinstance(result, int):
        return [{} for _ in range(result)]
    return list(result)


def run_all(checks: dict, parsed: dict) -> dict[str, list[dict]]:
    return {name: normalise_result(func(parsed))
            for name, func in checks.items()}
