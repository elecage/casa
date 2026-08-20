# release-traps — 과정을 재기 위한 과제 저장소

설계는 `DESIGN.md`, 함정 목록은 `docs/PROCESS_TRAPS.md`, 회복 판정과 달성 항목은
`docs/RECOVERY_RULE.md`.

`template/`이 세션에게 주어지는 저장소다. **시작 시점에 도구가 돌고 보이는
테스트가 전부 초록이다.** 틀린 것은 코드가 아니라 기록과 실제의 어긋남과,
완료까지 가는 길에 놓인 함정들이다.

과제 저장소가 조용히 순해지지 않도록 `tests/test_release_traps_template.py`가
함정마다 "심어 둔 조건"을 확인한다. 과제 저장소를 손볼 때 그 파일도 같이 본다.
