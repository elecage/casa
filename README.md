# CASA — Coding Agent Session Auditor

Black-box, user-side auditing for Claude Code sessions. CASA answers two
questions about a finished (or running) session, using only local data:

1. **Did the agent obey your persistent instructions** (CLAUDE.md /
   memory.md), expressed as machine-checkable rules?
2. **Did it behave well** — explore before editing, avoid repetition loops,
   keep tool errors low?

No model internals, no server access. Everything runs from the session
transcript (`~/.claude/projects/**/*.jsonl`) and Claude Code hooks.

This is also the artifact of a research project on persistent-instruction
compliance and black-box session-failure prediction. Start with
`docs/RESEARCH_PLAN.md`.

## Quick start

```bash
pip install -e .

# Score a session
casa audit ~/.claude/projects/<proj>/<session>.jsonl \
    --rules rules/rules.example.yaml

# JSON for analysis pipelines
casa audit <session>.jsonl --rules rules/canary_rules.yaml --json --out out.json
```

## Enforcement mode (hooks)

Merge `hooks/settings.example.json` into your project's `.claude/settings.json`.
Rules with `action: block` are stopped before execution (PreToolUse, exit 2);
`action: log` rules are recorded to `.casa/events.jsonl`. The Stop hook writes
a scorecard to `.casa/reports/` after every session.

## Layout

- `src/casa/` — transcript parser, metrics, rule engine, CLI
- `hooks/` — PreToolUse guard, Stop auditor, example wiring
- `rules/` — enforceable rule specs (YAML); `canary_rules.yaml` is the pilot set
- `docs/` — research plan, pilot design, related work, architecture
- `scripts/` — pilot procedure and canary CLAUDE.md template

## Design principles

Enforcement lives in code, never in prompts. The audit core is deterministic —
LLM judges are auxiliary only (they run ~70% precision; see
`docs/RELATED_WORK.md`). The parser is tolerant: the transcript format is
undocumented, so unknown shapes are skipped, never fatal.

## Status

v0.1.0 — pilot-ready skeleton. Tests: `python3 -m pytest`.
