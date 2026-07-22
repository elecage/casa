# STATUS — 세션 인수인계 파일

새 세션은 CLAUDE.md 필독 문서 다음에 이 파일을 읽는다. 작업 상태가 바뀌면
**같은 커밋에서** 이 파일을 갱신한다. 규칙은 CLAUDE.md의 "Session handoff" 절.

## 다음 세션 시작점

**W1 (buggy-pipeline 템플릿 레포 제작)** 부터. 사양은 `docs/PILOT_TASKS.md`.
`pilot/tasks/buggy-pipeline/{template/, prompt.txt, grade.py, relevant_files.txt}`
구조로 만든다.

## 작업 분해 (파일럿까지)

| ID | 작업 | 상태 | 산출물 |
|---|---|---|---|
| W1 | buggy-pipeline 템플릿 + 채점기 | 대기 | `pilot/tasks/buggy-pipeline/` |
| W2 | plugin-add 템플릿 + 채점기 (+ search-before-write 규칙 구체화) | 대기 | `pilot/tasks/plugin-add/` |
| W3 | rename-sweep 템플릿 + 채점기 | 대기 | `pilot/tasks/rename-sweep/` |
| W4 | 세션 러너 (반복 실행, 버전 기록, 트랜스크립트 수집) | 대기 | `pilot/run_sessions.py` |
| W5 | 궤적 지표 확장 (스텝별 누적 시계열, 궤적 유사도) | 대기 | `src/casa/metrics.py` 확장 |
| W6 | 집계·분석 (`casa report`: 분산 통계, AUROC@k) | 대기 | `src/casa/cli.py` + ARCHITECTURE 동기화 |
| W7 | 난이도 보정 (과제당 2~3세션, 40~80% 확인) | 대기 | 보정 기록 → 이 파일 |
| W8 | 파일럿 본 수집 (과제 3 × 15~20세션) | 대기 | `results/` |
| W9 | 분석 + go/no-go (PILOT_DESIGN 사전 등록 기준) | 대기 | 분석 노트 |

상태 값: 대기 / 진행 중 / 완료 / 보류(사유 명기). 의존성: W1~W3 병렬 가능,
W4는 W1 이후 권장(실물 과제로 시험), W7은 W1~W4+W5 필요, W8은 W7 필요.

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

## 미해결 / 주의

- 파일럿 러너(W4)가 클로드 코드를 헤드리스로 반복 실행하는 방법(권한 모드,
  `claude -p` 등)은 W4 착수 시 조사 필요 — 아직 검증 안 됨.
- rules/canary_rules.yaml의 `canary-search-before-write`는 플레이스홀더
  (빈 패턴 = 위반 발생 불가). W2에서 구체화하기로 함.
- 투고 직전 재확인: 최근접 프리프린트 2편의 개정/심사 상태 + ICSE/FSE/ICLR
  워크숍 동시 연구 표적 검색 (RELATED_WORK "열린 확인 사항").
