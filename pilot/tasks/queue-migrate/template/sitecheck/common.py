"""여러 검사가 함께 쓰는 코드."""

from __future__ import annotations


def normalise_location(raw: str) -> str:
    """경로 표기를 하나로 맞춘다. 슬래시와 끝의 구분자를 정리한다."""
    return raw.replace("\\", "/").rstrip("/").strip()


def within_window(value: int, start: int, end: int) -> bool:
    """구간 안인가. **끝값을 포함하지 않는다.**"""
    return start <= value < end
