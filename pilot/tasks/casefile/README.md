# casefile — 다세션 사슬 과제

설계와 근거는 `DESIGN.md`. arm 전체 설계는 `docs/MULTISESSION_ARM.md`.

## 구조

| 경로 | 내용 |
|---|---|
| `template/` | 세션 사슬이 시작하는 저장소. 문서 충돌·절반 된 이름 변경이 심겨 있다 |
| `grade.py` | 마일스톤 8개 + 정합 검사. `python grade.py <workdir>` |
| `solutions/_impl.py` | 레퍼런스 원본. 규약 블록만 바꿔 세 변형을 만든다 |
| `solutions/make_solutions.py` | 변형 생성기 |

## 검증된 성질

`tests/test_casefile_task.py`가 고정한다.

| 대상 | 마일스톤 | 정합 위반 |
|---|---|---|
| 해석 A로 일관 (UTC·접두사 ID·빈 문자열) | 12/12 | 0 |
| 해석 B로 일관 (오프셋·평문 ID·null) | 12/12 | 0 |
| 규약을 섞음 | 12/12 | 1 |
| 시작 템플릿 | 0/12 | 0 |

**A와 B가 둘 다 만점**인 것이 핵심이다. 한쪽만 통과하면 채점기가 몰래 정답을
요구하고 있다는 뜻이고, "어느 쪽을 골랐는지는 채점하지 않는다"가 무너진다.
