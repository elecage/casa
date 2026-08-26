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

- **지켜지지 않으면 안 되는 규칙은 그 행동을 막는 훅으로 구현한다.**
  `CLAUDE.md`, `harness/anchor.md`, 과제 프롬프트에만 적힌 규칙은 요청이지
  장치가 아니다 — 이 저장소에는 그런 규칙이 지켜지지 않은 기록이 여럿 있다
  (수집 배치 일곱 세션이 3주 동안 기록되지 않았고, 글쓰기 규칙을 읽은 세션이
  같은 세션 안에서 그 규칙을 어겼다).

  여기서 나오는 것이 둘이다.

  1. **우리 세션이 지켜야 하는 것은 훅을 만든다.** 문서에 적는 것으로 끝내지
     않는다. **목표·배경·현재 상태를 프롬프트로 전달하는 것은 여기 해당하지
     않는다** — 이 규칙이 말하는 것은 규칙이지 정보가 아니다. 그러므로
     `harness/anchor.md` 가 목표를 주입하는 것 자체는 이 규칙 위반이 아니다.
  2. **연구 대상 세션에게 주는 규칙은 훅으로 강제하지 않는다.** 그 규칙을
     지키는지가 우리가 측정하려는 것이므로, 강제하면 세션이 아니라 우리
     장치를 측정하게 된다.

  (2026-08-26에 고쳐 적었다. 앞 문장은 "Enforcement lives in code (hooks),
  never in prompts. A prompt-level rule is a measurement subject here, not a
  mechanism." 이었다. 유저 물음 — 사람이 읽어도 뜻이 분명하지 않고, 모델이
  오해하지 않는다고 볼 수 있느냐. 실제로 넷이 정해져 있지 않았다.
  ① `Enforcement` 가 막는 것만인지 알리는 것도 포함인지, ② `never` 를 문자
  그대로 읽으면 규칙이 서른 개 가까이 적힌 `CLAUDE.md` 자신이 위반이 되는 것,
  ③ 어느 프롬프트인지 — 우리 세션이 받는 것과 연구 대상 세션이 받는 것이 뜻이
  다른데 한 문장에 있었던 것, ④ `here` 의 범위. 2026-08-26 세션이 이 문장을
  근거로 앵커 전체를 위반이라고 읽은 사례가 있다.)
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
- **세션을 끝내기 직전에 인계를 남긴다** (2026-08-21 유저 지시). 규약을
  문서에 적어 두는 것만으로는 지켜지지 않았다 — 수집 배치 일곱 세션 분량이
  3주 동안 기록되지 않았다. 그래서 `harness/handoff_check.py`가 **Stop
  훅으로** 확인한다: 파일을 고쳤는데 `STATUS.md`를 손대지 않고 끝내려 하면
  세션당 한 번 되돌려보낸다. pre-commit 훅과 보는 것이 다르다 — 그쪽은
  커밋마다, 이쪽은 **세션이 끝나는 시점에** 다음 세션이 이어받을 것이 적혀
  있는지 본다. 커밋을 안 하고 끝내는 세션은 pre-commit 훅에 안 걸린다.
  끝내기 전에 셋을 적는다: **이번 세션이 한 일, 남은 일, 다음 세션 시작점.**

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
- **한 번 틀린 것으로 확인된 사실 주장은 목록에 넣는다** (2026-08-26 유저 지시
  — "기존의 레거시 문제들이 자꾸 튀어나오면 안돼"). 한 자리를 고치는 것으로는
  같은 문장이 다시 나오는 것을 막지 못했다: 옛 과제 열한 종에 대한 틀린 문장이
  `harness/anchor.md` 에서 다른 파일 다섯으로 옮겨 적혔고, 앵커를 고친 뒤에도
  나머지 다섯이 남아 유저가 다시 물어서야 드러났다. 목록은
  `harness/claim_rules.json` 이고, `harness/check_claims.py` 가 pre-commit 에서
  파일을, `harness/claim_check.py` 가 Stop 훅으로 마지막 답을 본다.
  **유저가 지적한 사실 오류 하나가 목록 항목 하나가 된다** — 유저가 지적할
  때마다 `harness/wording_rules.json` 에 항목이 하나씩 더해지는 것과 같다.
  항목은 틀린 서술과 그 서술의 대상을 짝으로 적는다(같은 표현이 다른 대상에
  대해서는 맞는 말일 수 있다). 틀린 문장을 이름으로 부를 때는 백틱으로 감싼다.

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
  **여기에는 개수만 말하고 무엇인지 말하지 않는 것이 포함된다** (2026-08-26
  유저 지적 — "두 가지는 일부러 열어 두었습니다. -> 이렇게 말하면 두 가지가
  뭔지 어떻게 알아"). 개수를 말하는 자리에서 그 자리에 무엇인지를 함께 적는다.
  **이것은 훅이 못 본다** — 무엇을 가리키는지는 문자열 대조로 판정되지 않는다.
  `harness/README.md` 의 "무엇을 못 막는가" 에 적어 두었다.

How to comply: prefer the plain sentence over any name. If a name is
unavoidable, define it in one line where it first appears, and check whether
the project already uses a different word for the same thing. Terms already in
`STATUS.md` and `docs/` stay as they are, but when you reuse one in a report,
define it in one line at first use.

Scope: replies to the user, commit messages, PR descriptions, and new docs.

**이 규칙은 훅이 확인한다** (2026-08-24 유저 지시로 신설). 문서에만 두었더니
2026-08-23 세션이 두 번, 2026-08-24 세션이 다시 어겼다 — 한 번 지적받은 말을
같은 세션 안에서 또 썼다. 그래서 `harness/wording_check.py`가 **Stop 훅으로**
마지막 답을 보고, 금지 목록(`harness/wording_rules.json`)의 말이나 분모를 안
밝힌 비율이 있으면 세션당 한 번 되돌려보낸다.

- **유저가 지적한 말 하나가 목록 항목 하나가 된다.** 지적을 받으면 그 자리에서
  목록에 더한다. 그것이 이 목록이 자라는 방식이다.
- **금지어를 이름으로 부를 때는 백틱으로 감싼다** — 검사가 인라인 코드와 코드
  블록과 인용 줄을 빼고 본다. 그렇게 하지 않으면 위반을 정정하는 답 자체가
  차단된다.
- 목록을 고칠 때는 `harness/wording_scan.py`로 실제 기록에 실행해 무엇이
  잘못 검출되는지 먼저 확인한다.

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
