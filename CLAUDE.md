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

## Session harness (guardrails on this repo's own sessions)

`harness/` holds machine-enforced guardrails for **our** dev sessions — do not
confuse it with `hooks/`, which is the instrument that audits the sessions we
*study*. It exists because the prompt-level rules above did not hold on their
own: a 7-session collection batch sat unrecorded for three weeks despite the
same-commit rule. Read `harness/README.md` before changing anything under it.

- `harness/gates.json` is the lock state. While `collection.state` is
  `locked`, running `pilot/run_sessions.py` is blocked at the tool-call level.
  **Never flip it to `open` without user approval**, and record the reason in
  the STATUS.md decision log in the same commit.
- New tasks under `pilot/tasks/` need a `DESIGN.md` answering
  `harness/TASK_DESIGN_RUBRIC.md` in full; the pre-commit hook rejects them
  otherwise. The 11 pre-existing tasks are grandfathered in
  `harness/legacy_tasks.txt` — that list must not grow.
- Report in plain language: internal labels (RQ2, F1, W15) and undefined
  statistics terms trigger a Stop-hook block once per session.

## How to write (2026-08-21, user instruction — applies from now on)

The reader has to be able to check the claim. Compressed or invented wording
makes that impossible, and in this project it has hidden real defects: a
grader condition that never ran once was reported for weeks as a passing
checkpoint. Three bans, all of them broken on 2026-08-21:

- **No coined terms.** Do not invent a name for a concept, and do not use a
  word the field does not actually use for it. Write the sentence out instead.
  Coined here and not to be repeated: "함정 기회" (say "그 세션이 그 함정에
  빠질 수 있는 자리를 지나갔는지"), "말끝을 맞추다" (say "고른 쪽과 문서가
  서로 맞는지"), "눈금" (say "달성 항목 통과 수"), "두 끝" (say "시작 상태와
  레퍼런스 해답").
- **No metaphors.** A grader condition is not "죽어 있다" — it "한 번도
  실행되지 않는다". A session does not "일을 삼킨다" — it "항목을 한 세션에 다
  채운다". If the literal sentence is longer, use the longer sentence.
- **No compression that drops the subject or the mechanism.** "확인의 깊이가
  문제다" says nothing checkable. Say who did what and how it was observed:
  "18세션 전부가 명세 문서와 코드를 둘 다 열었는데, 값이 틀린 어댑터 둘은
  아무도 못 찾았다".

How to comply: prefer the plain sentence over any name. If a name is
unavoidable, define it in one line where it first appears, and check whether
the project already uses a different word for the same thing. Terms already in
`STATUS.md` and `docs/` stay as they are, but when you reuse one in a report,
define it in one line at first use.

Scope: replies to the user, commit messages, PR descriptions, and new docs.

### 구어체를 쓰지 않는다 (2026-08-21, 유저 지시)

**유저가 구어체로 말해도 답은 문어체로 쓴다.** 논문과 기술 문서에서 쓰는
표현을 쓴다. 대화체 동사를 그대로 문서에 옮기면 뜻이 흐려진다 — `재다`는
`측정하다`인지 `추정하다`인지 `판정하다`인지가 문장에서 드러나지 않는다.

이 프로젝트에서 실제로 쓰고 있던 구어체와 바꿔 쓸 말:

| 구어체 | 문어체 |
|---|---|
| 재다 | 측정한다 / 판정한다 / 산출한다 (뜻에 맞는 것을 고른다) |
| 돌리다 (배치를) | 실행한다 |
| 잘리다 (세션이) | 중단된다 |
| 걸리다 (예산에) | 제한에 도달한다 |
| 집다 (남은 일을) | 이어받는다 / 착수한다 |
| 벌 (사슬 여섯 벌) | 회 / 개 (사슬 여섯 개) |
| 삼키다, 죽어 있다, 접는 선 | 비유 금지 규칙에서 이미 다룬다 |

**적용 범위는 위 Scope와 같다** — 유저에게 보내는 답, 커밋 메시지, PR 설명,
새로 쓰는 문서. **이미 있는 문서의 표현은 그대로 둔다.** 전부 고쳐 쓰면
변경 이력이 뜻 없이 커지고, 무엇이 실제로 바뀌었는지 읽기 어려워진다.

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
