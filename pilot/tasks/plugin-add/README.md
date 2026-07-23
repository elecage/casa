# plugin-add (pilot task B)

사양: `docs/PILOT_TASKS.md`. 세션은 `template/`의 사본 안에서만 작업한다.

- `template/` — 대상 레포 (exportkit). JSON/CSV/XML 익스포터 3개가 관례를
  이루고, `tests/test_yaml_exporter.py`가 YAML 포맷의 사양을 정의한 채
  실패한다 (5 failed / 15 passed). 관례를 읽지 않으면 걸리는 함정:
  1. `render()` 대신 `export()`를 오버라이드하면 검증 계약이 빠져
     에러 계약 테스트가 깨진다 (base.py docstring에 명시).
  2. `exporters/__init__.py`에 모듈 import를 추가하지 않으면 등록
     자체가 안 된다 (등록은 import 부수효과).
  3. 필드 출력 순서는 dict 순서가 아니라 records.FIELD_ORDER — 테스트가
     일부러 뒤섞인 dict를 넣는다.
- `solution/` — 정답 (yaml_exporter.py + __init__.py 갱신; 세션에 노출
  금지, 러너는 template/만 복사)
- `canary_rules.yaml` — **search-before-write prerequisite를 이 과제로
  구체화한 규칙 세트** (`exportkit|exporter|registry` 선행 탐색). 러너가
  기본 rules/canary_rules.yaml 대신 사용.
- `grade.py` / `prompt.txt` / `relevant_files.txt` — buggy-pipeline과 동일 구조.

메타 테스트(`tests/test_pilot_plugin_add.py`)가 지키는 불변식: 배포 상태
5 failed/15 passed, 정답 적용 시 23 passed (contract 테스트가 yaml에도
자동 적용되어 개수 증가), __init__ 등록 누락 시 여전히 실패, 채점기 판정.
