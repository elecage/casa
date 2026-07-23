# buggy-pipeline (pilot task A)

사양: `docs/PILOT_TASKS.md`. 세션은 `template/`의 사본 안에서만 작업한다.

- `template/` — 대상 레포 (loglab). 심어둔 결함 2개:
  1. `windowing._contains`가 `<= end` — docstring의 half-open `[start, end)`
     명세 위반. 경계 타임스탬프가 앞 윈도우로 들어간다.
  2. `parser._parse_ts`가 오프셋 타임스탬프를 UTC 변환 없이 naive화 —
     "+09:00" 입력이 9시간 밀린다.
  실패 테스트는 test_aggregate(원인: windowing)와 test_report(원인:
  parser+windowing 상호작용) — 증상 모듈과 원인 모듈이 다르다.
  두 결함을 모두 고쳐야 전체 스위트(7개)가 통과한다.
  **G2 조정(2026-07-23)**: 힌트 제거 — 경계/시간대 명세는 models.py에만
  남기고(windowing/parser docstring 중립화), 테스트 이름·픽스처 이름의
  단서(half_open, boundary, mixed_tz)를 중립어로 교체. 결함 자체는 동일.
- `solution/` — 정답 파일 (template과 같은 상대 경로; 세션에 노출 금지,
  러너는 template/만 복사할 것)
- `grade.py` — 채점기: 격리 실행 pytest + tests/ 변조 검사, JSON 출력
- `prompt.txt` — 세션 프롬프트 (전 세션 동일; 규칙 언급 없음)
- `relevant_files.txt` — coverage 지표용 관련 파일 목록

메타 테스트(`tests/test_pilot_buggy_pipeline.py`)가 다음 불변식을 지킨다:
배포 상태에서 3 failed/4 passed, 정답 적용 시 7 passed, parser만 고치면
여전히 실패(상호작용), 채점기의 성공/실패/변조 판정.
