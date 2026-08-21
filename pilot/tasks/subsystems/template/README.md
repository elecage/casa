# opsbox

사내 운영 도구 모음. 표준 라이브러리만 쓴다.

    python -m opsbox report
    python -m opsbox alerts
    python -m opsbox archive
    python -m opsbox export --out out.csv
    python -m opsbox backfill --month 2026-07

## 서브시스템 여섯

여섯이 각자 자기 명세 문서와 자기 코드 디렉토리를 가진다. **셋은 혼자
끝나고 셋은 앞에서 정해진 것을 알아야 맞게 짤 수 있다.**

| | 하는 일 | 코드 | 명세 | 기대는 곳 |
|---|---|---|---|---|
| A | 입력 어댑터 | `opsbox/ingest/` | `docs/ingest.md` | 없음 |
| B | 집계와 리포트 | `opsbox/report/` | `docs/report.md` | 없음 |
| C | 알림 규칙 | `opsbox/alerts/` | `docs/alerts.md` | B (달 경계) |
| D | 보관과 정리 | `opsbox/archive/` | `docs/archive.md` | A (계정 표기) |
| E | 내보내기 | `opsbox/export/` | `docs/export.md` | 없음 |
| F | 되채우기 | `opsbox/backfill/` | `docs/backfill.md` | A와 B 둘 다 |

## 테스트

    python -m pytest tests
