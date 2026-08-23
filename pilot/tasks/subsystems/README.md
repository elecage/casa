# subsystems — 한 세션에 안 들어가는 과제 저장소

`template/`(과제 저장소), `grade.py`(달성 항목 열일곱), `detect.py`(함정
열셋), `solutions/complete.py`(레퍼런스 해답)가 다 있다. 설계는 `DESIGN.md`,
함정 목록은 `docs/PROCESS_TRAPS.md`.

**과제 저장소와 두 프롬프트는 영어로 쓴다**(2026-08-21 유저 지시). 판정에
쓰는 문자열도 영어다 — `Decision:` 줄, `local time`/`UTC`,
`hyphen`/`slash`, `lowercase`/`uppercase`, `age`/`size`,
`whole month`/`last observation`. `tests/test_subsystems_template.py`가
저장소에 한글이 한 글자도 없는지 확인한다.

이름 뜻: 서브시스템 여섯을 한 릴리스에 담아야 하는데 한 세션이 그것을 다 볼
수 없는 과제라는 뜻이다. "서브시스템"은 자기 명세 문서와 자기 입력 파일과 자기
코드 디렉토리를 따로 가진 덩어리를 말한다.

`release-traps`와 무엇이 다른가: 저장소가 한 세션의 맥락에 안 들어간다.
그래서 세션이 무엇부터 할지 골라야 하고, 다음 세션은 자기가 안 읽은 부분을
물려받는다. 서브시스템 여섯 중 셋은 앞서 정해진 선택을 알아야 맞게 짤 수
있어서, **인계 문서에 처음으로 실제 정보가 실린다.**
