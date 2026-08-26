# sitecheck

설정 파일을 읽어 규칙 위반을 보고하는 사내 도구다. 배포 전에 각
사이트의 설정이 우리 규칙을 지키는지 확인하는 데 쓴다.

## 구성

| 자리 | 무엇 |
|---|---|
| `sitecheck/checks/` | 검사 하나에 파일 하나. 규칙 하나를 본다 |
| `sitecheck/legacy_registry.py` | 옛 등록 방식. 이름과 함수를 손으로 묶어 둔 표 |
| `sitecheck/registry.py` | 새 등록 방식. 검사 파일이 스스로 등록한다 |
| `sitecheck/report.py` | 검사 결과를 보고서로 만든다 |
| `docs/checks/` | 검사마다의 기대 동작 |
| `fixtures/` | 검사에 쓰는 표본 설정과 목록 |

테스트는 `python -m pytest tests/` 로 실행한다.

## 지금 하고 있는 일

검사를 옛 등록 방식에서 새 방식으로 옮기고 있다. 계획은
`docs/plan.md`, 남은 것과 순서는 `NEXT.md`, 지금까지의 경과는
`HANDOFF.md` 에 있다.
