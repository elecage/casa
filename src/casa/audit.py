"""Session scorecard: metrics + rule violations -> dict / markdown report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import metrics as m
from .rules import Rule, evaluate
from .transcript import parse


def audit_session(
    transcript_path: str | Path,
    rules: list[Rule] | None = None,
    relevant_files: list[str] | None = None,
    trajectory: bool = False,
) -> dict[str, Any]:
    session = parse(transcript_path)
    result: dict[str, Any] = {
        "transcript": str(transcript_path),
        "metrics": m.compute_all(session, relevant_files),
        "census": m.tool_census(session),
        "violations": [],
    }
    if trajectory:
        result["trajectory"] = {
            "steps": m.step_series(session, relevant_files),
            "tool_sequence": m.tool_sequence(session),
        }
    if rules:
        violations = evaluate(session, rules)
        result["violations"] = [v.to_dict() for v in violations]
        pre = sum(1 for v in violations if v.after_compaction == 0)
        post = len(violations) - pre
        result["violation_summary"] = {
            "total": len(violations),
            "by_kind": {
                "prohibition": sum(1 for v in violations if v.kind == "prohibition"),
                "obligation": sum(1 for v in violations if v.kind == "obligation"),
            },
            "pre_compaction": pre,
            "post_compaction": post,
        }
    return result


def to_markdown(result: dict[str, Any]) -> str:
    met = result["metrics"]
    lines = [
        "# CASA Session Scorecard",
        "",
        f"Transcript: `{result['transcript']}`",
        "",
        "## Behavioral metrics",
        "",
        f"- Tool calls: {met['n_tool_calls']} "
        f"(errors: {met['tool_error_rate']:.1%})",
        f"- Exploration before first edit: {met['exploration_before_first_edit']}",
        f"- Files read: {met['files_read_count']}"
        + (f" — coverage {met['coverage']:.0%}" if met.get("coverage") is not None else ""),
        f"- Max repetition: {met['max_repetition']} "
        f"(consecutive: {met['consecutive_repetition']})",
        f"- Compaction events: {met['compaction_count']}",
        f"- Model version(s): {', '.join(met['model_versions']) or 'unknown'}",
    ]
    census = result.get("census")
    if census and census.get("shell_like_unrecognized"):
        lines.append(
            f"- **⚠ unrecognized shell-like tools: "
            f"{', '.join(census['shell_like_unrecognized'])}** — audit may "
            f"undercount shell activity; update parser before trusting it.")
    vs = result.get("violation_summary")
    if vs is not None:
        lines += ["", "## Rule violations", ""]
        if vs["total"] == 0:
            lines.append("No violations detected.")
        else:
            lines.append(
                f"**{vs['total']} violation(s)** — "
                f"prohibition: {vs['by_kind']['prohibition']}, "
                f"obligation: {vs['by_kind']['obligation']} | "
                f"pre-compaction: {vs['pre_compaction']}, "
                f"post-compaction: {vs['post_compaction']}"
            )
            lines.append("")
            for v in result["violations"]:
                lines.append(
                    f"- [{v['severity']}] `{v['rule_id']}` at call #{v['call_index']}"
                    f"{' (post-compaction)' if v['after_compaction'] else ''}: {v['detail']}"
                )
    return "\n".join(lines) + "\n"


def to_json(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)
