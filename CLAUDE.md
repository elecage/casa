# CASA — Coding Agent Session Auditor

Research project: black-box, user-side auditing of closed commercial coding
agents (Claude Code). Detects sessions that violate persistent instructions
(CLAUDE.md/memory.md) or under-explore before answering, using only local
transcripts (JSONL) and hooks. No model internals, no server access.

## Context you must read first

- `docs/RESEARCH_PLAN.md` — research questions, contribution package, risks, target venues
- `docs/PILOT_DESIGN.md` — canary-rule pilot: what to run before committing to the full study
- `docs/PILOT_TASKS.md` — the three pilot task specs (buggy-pipeline / plugin-add / rename-sweep)
- `docs/RELATED_WORK.md` — prior work map; do not re-derive novelty claims, extend this file
- `docs/ARCHITECTURE.md` — module layout and design principles

## Design principles (do not violate)

- Enforcement lives in code (hooks), never in prompts. A prompt-level rule is
  a measurement subject here, not a mechanism.
- The audit engine must stay deterministic. LLM-as-judge is an optional,
  clearly-labeled auxiliary signal only (judges have ~70% precision; see
  AgentRewardBench in RELATED_WORK).
- The transcript parser (`src/casa/transcript.py`) must be tolerant: the JSONL
  format is undocumented and version-dependent. Unknown fields/lines are
  skipped, never fatal.
- Metrics must be computable per-session with no ground-truth labels
  (labels come from task outcomes in experiments, not from the tool).

## Working rules

- Always use the project venv at `.venv/` for every Python command (install,
  pytest, running the CLI). On Windows: `.venv\Scripts\python.exe`; on
  POSIX: `.venv/bin/python`. If `.venv/` is missing, create it with
  `python -m venv .venv` and install with `pip install -e ".[dev]"`.
  Never install into or run against the system Python.
- Run `.venv\Scripts\python.exe -m pytest` (Windows) / `.venv/bin/python -m pytest`
  (POSIX) before every commit. Do not commit failing tests.
- Never edit `tests/fixtures/*.jsonl` to make a test pass; fix the code.
- Keep dependencies to stdlib + PyYAML. Justify any new dependency in the PR/commit message.
- Update `docs/` in the same commit when behavior or study design changes.
