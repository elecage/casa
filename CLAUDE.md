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

## Session handoff (multi-session project — follow strictly)

- Read `STATUS.md` right after the docs above. It holds the work breakdown
  (W1..W9), current states, the decision log, and where the next session
  should start.
- When a work item changes state (started, finished, blocked), update
  `STATUS.md` **in the same commit** as the work itself.
- Decisions that override or refine the docs go to the STATUS.md decision
  log with a date; never leave them only in conversation.
- Before ending a session: make sure "다음 세션 시작점" in STATUS.md is
  accurate, and commit or explicitly note any uncommitted work there.
- Do not re-litigate logged decisions; ask the user before reversing one.

## Working rules

- Always use the project venv at `.venv/` for every Python command (install,
  pytest, running the CLI). On Windows: `.venv\Scripts\python.exe`; on
  POSIX: `.venv/bin/python`. If `.venv/` is missing, create it with
  `python -m venv .venv` and install with `pip install -e ".[dev]"`.
  Never install into or run against the system Python.
- One-time per clone: `git config core.hooksPath scripts/git-hooks` — the
  pre-commit hook machine-enforces "tests pass" and "no direct commits to
  main". If a commit is rejected, fix the cause; do not bypass with -n.
- Run `.venv\Scripts\python.exe -m pytest` (Windows) / `.venv/bin/python -m pytest`
  (POSIX) before every commit. Do not commit failing tests.
- **Every code change ships with tests in the same commit/PR.** New feature →
  tests proving the behavior; bug fix → regression test that fails before the
  fix. Docs-only and rules-YAML-only changes are exempt.
- **All changes reach `main` via pull request, and merge only when the CI
  workflow (`.github/workflows/ci.yml`: pytest on Ubuntu/Windows × Python
  3.10/3.13) is green.** Work on a feature branch (`w1-buggy-pipeline`-style
  names), push, open the PR with `gh pr create`, wait for CI, then merge.
  Do not push directly to main.
- Never edit `tests/fixtures/*.jsonl` to make a test pass; fix the code.
- Keep dependencies to stdlib + PyYAML. Justify any new dependency in the PR/commit message.
- Update `docs/` in the same commit when behavior or study design changes.
