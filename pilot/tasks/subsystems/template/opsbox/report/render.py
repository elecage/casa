"""리포트를 텍스트로 적는다. 절 구성은 `docs/report.md`."""

from __future__ import annotations

from .dates import format_date


def render_text(report: dict, generated_at=None) -> str:
    lines = ["# opsbox 사용량 리포트", ""]
    if generated_at is not None:
        lines += [f"작성일: {format_date(generated_at)}", ""]
    lines += ["## 합계", "",
              f"기록 {report['record_count']}건, 사용량 {report['total_units']}",
              "", "## 원천별", ""]
    for name, value in report["by_source"].items():
        lines.append(f"- {name}: {value}")
    lines += ["", "## 계정별", ""]
    for name, value in report["by_account"].items():
        lines.append(f"- {name}: {value}")
    lines += ["", "## 달별", ""]
    for key, value in report["by_month"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"
