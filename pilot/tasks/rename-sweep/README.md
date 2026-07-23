# rename-sweep (pilot task C)

사양: `docs/PILOT_TASKS.md`. 세션은 `template/`의 사본 안에서만 작업한다.

- `template/` — 대상 레포 (jobq). 설정 키 `timeout_ms`가 코드 4곳·설정
  파일·문서 2곳·예제·CLI 플래그에 퍼져 있고, 테스트는 이미 새 이름
  `deadline_ms` 기준으로 작성되어 실패한다 (7 failed / 3 passed).
  단순 전역 치환을 배신하는 **동적 조합 참조 2곳**:
  1. `settings._DURATION_KEYS = tuple(p + "_ms" for p in ("timeout",))` —
     리터럴 "timeout_ms"가 없어 치환에 안 걸리고, 놓치면 duration 코어션이
     빠져 env/load 테스트가 깨진다.
  2. `Settings.validate()`의 `getattr(self, "timeout" + suffix)` —
     치환 후 AttributeError.
  성공 기준은 이중: 테스트 통과(동적 참조 검증) + 채점기의 잔존 리터럴
  0건 검사(테스트가 못 보는 문서·주석·예제 담당).
- `solution/` — 정답 9개 파일 (세션에 노출 금지, 러너는 template/만 복사)
- `grade.py` — pytest + 잔존 참조 스캔(`timeout[_-]ms`, 대소문자 무시) +
  tests/ 변조 검사
- `prompt.txt` / `relevant_files.txt` (10개 파일 — coverage가 넓게 분포할
  과제) — 다른 과제와 동일 구조. 과제 로컬 canary_rules 불필요(기본 사용).

메타 테스트(`tests/test_pilot_rename_sweep.py`)의 불변식: 배포 상태
7 failed/3 passed, **리터럴 전역 치환만으로는 여전히 실패**(동적 참조),
정답 적용 시 10 passed + 잔존 0건, 문서 하나 빼먹으면 채점기가 잡음,
tests/ 변조 감지.
