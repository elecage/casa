# 아키텍처

```
CLAUDE.md (자연어 규칙)
        │  (수동/반자동 변환 — AgentSpec식 트리거·조건·조치)
        ▼
rules/*.yaml  ──────────────┐
        │                   │
        ▼                   ▼
[런타임 계층]          [감사 엔진]
hooks/pretooluse_guard  src/casa/
  - block 모드: 위반 차단   - transcript.py  JSONL 파서 (관용적)
  - log 모드: 기록만        - metrics.py     행동 지표 (+궤적 시계열)
hooks/stop_audit           - rules.py       규칙 매칭
  - 세션 종료 시 채점        - audit.py       스코어카드
                           - report.py      배치 집계 (AUROC@k, 보정, 기준선)
                           - cli.py         casa audit / casa report
```

## 저장소 지도 (2026-08-21 현재)

위 다이어그램은 **감사 엔진**만 그린 것이다. 실험을 돌리는 쪽이 그만큼 커졌다.

```
src/casa/            감사 엔진 (위 다이어그램)
  transcript.py      JSONL 파서 (관용적)
  metrics.py         행동 지표
  signals.py         초반 신호
  trap_state.py      네 상태 + 물려받았나 만들었나(blame)
  rules.py audit.py report.py cli.py

pilot/               실험을 돌리는 쪽
  run_sessions.py    단발 세션 배치
  run_chain.py       사슬 배치 — 세션들이 한 작업 디렉토리를 물려받는다
  snapshot.py        PostToolUse 훅. 호출마다 작업 트리를 커밋한다
  chain_budget.py    PreToolUse 훅. 세션당 도구 호출 예산
  analysis/
    chain_eval.py    사슬 평가 — 함정 벡터, 인계 판정, 초반 신호 고르기
    batch_summary.py 배치 숫자 요약 (봉인한 예측을 코드로 들고 있다)
    probe_eval.py    단발 배치 평가
    call_attribution.py  호출을 달성 항목에 귀속
    power.py         표본 크기 산정
  tasks/             과제 저장소들 (아래)

harness/             **우리 개발 세션**에 거는 가드레일 (hooks/ 와 다르다)
  gates.json         수집 잠금 상태
  anchor.md          목표와 열린 문제. 매 세션 자동 주입
  check_task_design.py  새 과제의 DESIGN.md 검문
  report_check.py    내부 약어로 보고하면 한 번 막는다

hooks/               **연구 대상 세션**에 거는 계측
```

### 과제 저장소 세 갈래

| 갈래 | 무엇 | 상태 |
|---|---|---|
| 옛 11종 (`harness/legacy_tasks.txt`) | "함수 하나가 비어 있고 명세는 완전하다" | 설계 검문 면제. **이 목록은 늘리지 않는다** |
| `casefile`, `release-traps` | 판단·상충·정합이 들어간 과제 | `release-traps`로 배치 셋(54세션)을 돌렸다 |
| `subsystems` | 서브시스템 여섯이라 한 세션에 안 들어간다 | 구현 끝, 아직 안 돌렸다 |

과제 하나는 이렇게 생겼다.

```
pilot/tasks/<name>/
  DESIGN.md          설계 검문 여덟 항목의 답 (없으면 커밋이 거부된다)
  prompt.txt         세션에게 주는 한 줄
  template/          세션이 받는 저장소. 시작 시 보이는 테스트가 초록이다
  hidden/            채점할 때만 갈아 끼우는 표본. 세션은 못 본다
  grade.py           달성 항목 판정. 판정 불가는 null
  detect.py          함정 상태 벡터 — **이것이 세션 점수다**
  attribute.py       호출을 항목에 귀속 (release-traps)
  solutions/         레퍼런스 해답. 양방향으로 만들어 어느 쪽도 만점인지 본다
```

## 전달 형태 — 외부 앱 (2026-08-19 유저 결정)

탐지기는 클로드 코드 프로세스 **밖**의 외부 앱이다. 트랜스크립트 JSONL을
따라 읽으며 진행 중 세션을 관찰하고, 사람에게 알린다. 위 다이어그램의
훅 계층은 **연구용 계측**으로 남고, 제품 형태는 관찰 전용이다.

**실현 가능성 확인 (2026-08-19)**: 트랜스크립트는 세션 종료 후가 아니라
**메시지마다 실시간 덧붙여진다.** 진행 중이던 세션 파일의 마지막 줄
타임스탬프가 확인 시각보다 4초 전이었다(09:39:54Z 기록 / 09:39:58Z 확인,
634줄). 훅·설정 변경·프로젝트 결합 없이 초 단위 지연으로 관찰 가능.

| 동작 | 외부 앱 | 비고 |
|---|---|---|
| 진행 중 세션 관찰 | 가능 | 파일 따라 읽기 |
| 여러 프로젝트 동시 감시 | 가능 | 기록이 프로젝트별 디렉토리에 모여 있음 |
| 사람에게 알림 | 가능 | 본래 역할 |
| 세션 종료 | 가능 | 프로세스 종료는 결합 불요 |
| 도구 호출 차단 | **불가** | 프로젝트 설정 안의 훅이어야 함 |
| 세션에 말 끼워넣기 | **불가** | 같은 이유 |
| 특정 시점으로 되감기 | **불가** | 기능 자체가 없음 |

**지렛대는 알림과 종료 둘뿐이다.** 이 제약이 설계에 거는 것:

1. 지표는 **앞에서부터 순서대로** 계산 가능해야 한다(뒤를 미리 못 봄).
   세션이 끝나야 확정되는 지표는 사후 보고용으로 분리한다.
2. **기준선 학습에 의존하지 않아야 한다.** 새 사용자는 정상 세션이 0개이고,
   폐쇄 상용 도구는 배포가 통보 없이 바뀌어 기준선이 밑에서 움직인다.
   세션 자기 자신만 보고 판정되는 지표가 우선이다.
3. 헛경보 비용이 "사람의 주의 한 번"으로 싸지므로 **알림 문턱과 종료 권고
   문턱을 따로** 잡는다.
4. 알림 문구는 구체적이어야 한다("같은 명령 12회 반복, 파일 변화 없음").
   판단은 사람이 하고, 사람이 판단하려면 무엇이 걸렸는지 알아야 한다.

**미해결 위험**: 트랜스크립트 형식은 비공개·버전 종속이다. 파서는 관용적
이지만 **형식이 바뀐 것을 알아채는 장치가 없다.** 제품화 시 필요.

근거와 갭 분석은 `docs/COMPARISON_RUNTIME_MONITOR.md`, 지표 목록과 진행
중/종료 후 구분은 `docs/BADNESS_SIGNALS.md`.

## 원칙

1. **강제는 코드, 판단은 문서.** 기계 판정 가능한 규칙은 훅으로, 취향·방향성
   규칙만 CLAUDE.md에 남긴다. 감사 도구가 감사 대상과 같은 확률적 메커니즘
   위에 서면 안 된다.
2. **파서는 관용적으로.** 트랜스크립트 JSONL 포맷은 비공개·버전 종속.
   모르는 라인/필드는 건너뛰고 절대 죽지 않는다.
3. **결정론적 코어.** LLM 심판은 옵션이며 결과에 별도 표기.
4. **두 가지 훅 모드.** 실사용 = block(예방), 연구 = log-only(관찰).
   파일럿은 반드시 log-only.

## 훅 연결

`hooks/settings.example.json`(Linux/macOS) 또는
`hooks/settings.example.windows.json`(Windows)을 프로젝트
`.claude/settings.json`에 병합. 두 예시 모두 프로젝트 venv의 Python을
명시 호출한다(`.venv/bin/python` / `.venv\Scripts\python.exe`) — 시스템
Python에는 PyYAML이 없을 수 있고, 훅은 조용히 실패하면 안 되기 때문.
Windows에서 훅 커맨드는 Git Bash로 실행되므로 `$CLAUDE_PROJECT_DIR`
문법이 그대로 동작한다. 훅 스크립트는 stdout/stderr를 UTF-8로 재설정한다
(Windows 레거시 코드페이지에서 규칙 설명이 깨지는 것 방지).
PreToolUse는 stdin으로 {tool_name, tool_input, transcript_path}를 받고
exit 2 + stderr로 차단한다. Stop 훅은 transcript_path로 casa audit을 실행해
`.casa/reports/`에 스코어카드를 남긴다.

## 규칙 스키마 (rules/*.yaml)

- `type: prohibit` — tool + regex. 발생 즉시 위반. 훅에서 차단 가능.
- `type: require_before` — trigger(tool+regex) 발생 시 그 이전에
  prerequisite(tool+regex)가 있었는지 검사. 감사 시 판정, 훅에서는
  transcript_path 스캔으로 판정 가능.
- 공통 필드: id, description, severity(low/med/high), category(security/
  workflow/style), kind(prohibition/obligation — H1b 분석용 라벨)
