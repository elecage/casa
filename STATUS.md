# STATUS — 세션 인수인계 파일

새 세션은 CLAUDE.md 필독 문서 다음에 이 파일을 읽는다. 작업 상태가 바뀌면
**같은 커밋에서** 이 파일을 갱신한다. 규칙은 CLAUDE.md의 "Session handoff" 절.

## 다음 세션 시작점

**W1.5 (수직 슬라이스)** 부터. W1은 완료 — `pilot/tasks/buggy-pipeline/`에
템플릿(loglab, 결함 2개)·채점기·정답·메타 테스트까지 있다 (구조 설명은 그
디렉토리의 README.md). W1.5의 내용: 클로드 코드 헤드리스 반복 실행 방법을
조사·검증하고(`claude -p` 권한 모드 포함), buggy-pipeline 세션 2~3개를
실행→트랜스크립트 수집→casa audit→grade.py 채점까지 끝까지 돌린 뒤
**게이트 G1**을 기록하고 유저에게 보고한다.

## 작업 분해 (파일럿까지)

| ID | 작업 | 상태 | 산출물 |
|---|---|---|---|
| W1 | buggy-pipeline 템플릿 + 채점기 | **완료** (2026-07-22, PR #2) | `pilot/tasks/buggy-pipeline/` |
| W1.5 | **수직 슬라이스**: 러너 프로토타입으로 W1 과제 세션 2~3개를 끝까지 (실행→트랜스크립트 수집→casa audit→채점) | **진행 중** — 러너 초안·테스트 완료(PR #3), 세션 실행은 CLI 재인증 대기 | 러너 초안 + **게이트 G1 기록** |
| W2 | plugin-add 템플릿 + 채점기 (+ search-before-write 규칙 구체화) | 대기 | `pilot/tasks/plugin-add/` |
| W3 | rename-sweep 템플릿 + 채점기 | 대기 | `pilot/tasks/rename-sweep/` |
| W4 | 세션 러너 완성 (반복 실행, 버전 기록, 트랜스크립트 수집) | 대기 | `pilot/run_sessions.py` |
| W5 | 궤적 지표 확장 (스텝별 누적 시계열, 궤적 유사도) | 대기 | `src/casa/metrics.py` 확장 |
| W6 | 집계·분석 (`casa report`: 분산 통계, AUROC@k) | 대기 | `src/casa/cli.py` + ARCHITECTURE 동기화 |
| W7 | 난이도 보정 (과제당 2~3세션, 40~80% 확인) → **게이트 G2** | 대기 | 보정 기록 → 이 파일 |
| W8 | 파일럿 본 수집 (과제 3 × 15~20세션) | 대기 | `results/` |
| W9 | 분석 + go/no-go = **게이트 G3** (PILOT_DESIGN 사전 등록 기준) | 대기 | 분석 노트 |

상태 값: 대기 / 진행 중 / 완료 / 보류(사유 명기). 의존성: **W1 → W1.5(G1)
→ 나머지**. G1 통과 후 W2~W3 병렬 가능, W7은 W2~W5 필요, W8은 W7(G2) 필요.

## 방향 점검 게이트 (마일스톤 기반 — 시간 기반 아님)

각 게이트는 "다음 단계의 비용을 쓰기 전 마지막 지점"에 있다:

- **G1** (W1.5 직후, 템플릿 2개 더 만들기 전): 헤드리스 반복 실행·수집·감사·
  채점 파이프라인이 실제로 도는가? 안 돌면 여기서 멈추고 방법을 다시 찾는다.
- **G2** (W7 직후, 45~60세션 본 수집 전): 성공률이 40~80% 구간인가? 보정
  세션들의 행동 지표가 실제로 흩어지는가? 분산이 바닥이면 본 수집은 낭비다.
- **G3** (W9, 본 실험 전): PILOT_DESIGN 사전 등록 기준으로 go/no-go.

**모든 게이트에서 같은 질문 5개를 묻고 결과를 이 파일에 기록한다:**

1. 지난 게이트 이후 산출물이 논문의 척추(실증 발견)에 기여했는가, 도구
   장식이었는가? ("도구는 주인공이 아니다" — RESEARCH_PLAN)
2. 사전 등록 기준을 여전히 통과할 수 있어 보이는가? 아니라면 기준 수정
   vs 설계 수정 중 무엇인지 결정하고 결정 로그에 남긴다 (사후 조작 방지)
3. 노벨티 워치 (10분 arXiv 표적 검색): 2605.28840 / 2603.29231의 개정·후속
   + 신규 동시 연구. 발견 시 RELATED_WORK.md 갱신
4. 설계 원칙(CLAUDE.md) 위반 없는가 — 결정론적 코어, 프롬프트 강제 금지 등
5. **게이트 요약을 유저에게 보고하고 계속/조정 결정을 받는다**

### 게이트 기록

(아직 없음 — G1부터 여기에 날짜·판정·5문항 요약을 남긴다)

## 결정 로그 (뒤집으려면 유저와 상의)

- 2026-07-22 연구 초점 = **세션 간 변동성** (compaction/H1a 폐기, 공변량으로만
  기록). 유저가 명시 지시. → docs/RESEARCH_PLAN.md
- 2026-07-22 선행 연구 딥서베이 완료. 노벨티 스코핑: 실 코딩 에이전트 +
  within-run 조기 예측 + 블랙박스 + 준수×일관성 공분산. 최근접 경쟁:
  arXiv 2605.28840, 2603.29231. → docs/RELATED_WORK.md
- 2026-07-22 파일럿 과제 3종 확정 (buggy-pipeline / plugin-add /
  rename-sweep). → docs/PILOT_TASKS.md
- 2026-07-22 Python 환경 = 프로젝트 `.venv/` 필수. 훅도 venv python 명시
  호출 (Windows: `.venv\Scripts\python.exe`).
- 2026-07-22 GitHub private 저장소 https://github.com/elecage/casa 로 동기화.
- 2026-07-22 개발 규칙 강화: 모든 코드 변경은 테스트 동반, main 직접 push
  금지 — 피처 브랜치 + PR + CI(GitHub Actions, Ubuntu/Windows ×
  py3.10/3.13) 녹색이어야 머지. → CLAUDE.md Working rules
- 2026-07-22 하네스 완비: .gitattributes(줄바꿈 정규화), pre-commit 훅
  (scripts/git-hooks — pytest+main 커밋 차단, clone당 1회 core.hooksPath
  설정 필요), 프로젝트 .claude/settings.json(권한 허용 목록 + CASA 셀프
  감사 훅 배선 — hooks/run.sh 경유), PR 템플릿. 브랜치 보호는 무료 플랜
  private라 불가(관례+pre-commit으로 대체, public 전환 시 재시도).

## 미해결 / 주의

- **W1.5 블로커 (유저 액션 필요):** 헤드리스 `claude -p` 스모크 테스트가
  401 (OAuth 토큰 만료)로 실패. 유저가 터미널에서 `claude auth login`으로
  재인증해야 슬라이스 세션 실행 가능. CLI 2.1.172, 플래그(`-p`,
  `--output-format json`, `--dangerously-skip-permissions`)는 확인됨 —
  JSON 결과에 session_id·usage가 포함되는 것까지 검증 (401 응답에서 확인).
- rules/canary_rules.yaml의 `canary-search-before-write`는 플레이스홀더
  (빈 패턴 = 위반 발생 불가). W2에서 구체화하기로 함.
- 투고 직전 재확인: 최근접 프리프린트 2편의 개정/심사 상태 + ICSE/FSE/ICLR
  워크숍 동시 연구 표적 검색 (RELATED_WORK "열린 확인 사항").
