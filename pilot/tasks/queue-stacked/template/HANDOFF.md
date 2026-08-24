# 인계

## 지금까지

옛 등록 방식(`sitecheck/legacy_registry.py`)에서 새 방식
(`sitecheck/registry.py`)으로 검사를 하나씩 옮기는 중이다. 남은 것과
순서는 `NEXT.md` 가 한 번에 하나씩 보여 준다.

## 규율

- 항목을 끝낼 때마다 `docs/decisions.md` 에 `- <항목 번호>: <무엇을
  정했고 무엇을 했는지>` 형태로 한 줄을 적는다. 그래야 다음 항목이
  `NEXT.md` 에 나타난다.
- 항목마다 `python -m pytest tests/` 를 실행한다.

## 읽어 둘 것

- `RULES.md` — 하지 말 것.
- `CHANGELOG.md` — 무엇이 이미 됐는지.
- `docs/checks/` — 검사마다의 기대 동작.
