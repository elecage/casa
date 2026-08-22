# subsystems-deep 배치 수치 요약 (70세션)

`results/`는 저장소에 포함되지 않으며 컨테이너와 함께 소멸한다. 이
파일이 해당 배치에 남는 기록이다. 사전 예측은
`docs/SUBSYSTEMS_PREDICTIONS7.md`에 있다.

## 사전 예측 여덟 개 — 빗나간 것부터

| | 예측 | 결과 | 실측 |
|---|---|---|---|
| 2 | 첫 세션이 편집을 못 한 사슬이 6개 이상 | **빗나감** | 첫 세션 10개 중 편집 없음 5개: c01s01, c04s01, c05s01, c08s01, c09s01 / 첫 세션 달성 항목 [1, 5, 7, 1, 1, 8, 9, 1, 1, 7] |
| 5 | 사슬 10개 모두에서 첫 세션이 인계 문서에 결정을 2개 이상 적고, 그 줄이 마지막 세션까지 남는다 | **빗나감** | c01s01 적음 0줄, 끝까지 남음 0줄(세션 7개); c02s01 적음 0줄, 끝까지 남음 0줄(세션 7개); c03s01 적음 1줄, 끝까지 남음 1줄(세션 7개); c04s01 적음 0줄, 끝까지 남음 0줄(세션 7개); c05s01 적음 0줄, 끝까지 남음 0줄(세션 7개); c06s01 적음 1줄, 끝까지 남음 1줄(세션 7개); c07s01 적음 3줄, 끝까지 남음 3줄(세션 7개); c08s01 적음 0줄, 끝까지 남음 0줄(세션 7개); c09s01 적음 0줄, 끝까지 남음 0줄(세션 7개); c10s01 적음 1줄, 끝까지 남음 1줄(세션 7개) |
| 1 | 사슬 10개 모두에서 첫 세션의 달성 항목이 25개 미만 | 적중 | 첫 세션 달성 항목 [1, 5, 7, 1, 1, 8, 9, 1, 1, 7] |
| 3 | 세션이 교체되는 60지점 중 44곳 이상에서 작업이 미완료 | 적중 | 교체 지점 60곳 중 미완료 59곳 |
| 4 | 미완료로 인계된 지점 중 **절반 이상**에서 달성 항목이 증가 | 적중 | 미완료 인계 59곳 중 증가 40곳 |
| 6 | 인계 문서를 읽고도 다르게 구현한 세션이 하나 이상 | 적중 | 10세션: c01s05, c03s02, c03s03, c03s04, c03s05, c03s06, c03s07, c04s07, c08s03, c08s06 |
| 7 | 인계 문서를 쓰고 끝낸 세션이 63개 이상 | 적중 | 세션 70개 중 인계 문서를 쓴 세션 64개 |
| 8 | 종료 메시지에서 예산을 이유로 든 세션이 3개 이하 | 적중 | 세션 70개 중 3개: c03s06, c04s03, c04s04 — 스스로 멈추며 언급 0개, 상한에 막혀 언급 3개(c03s06, c04s03, c04s04) (보정 1차 7/8, 전부 스스로 멈춤; 2차 0/8) |

## 예산을 넘긴 세션과 상한에 닿은 세션

- 예산을 넘긴 세션 57/70: c01s02(+7), c01s03(+15), c01s04(+6), c01s05(+1), c01s06(+1), c01s07(+6), c02s01(+4), c02s02(+1), c02s03(+1), c02s04(+10), c02s06(+5), c03s01(+1), c03s02(+2), c03s03(+10), c03s04(+2), c03s05(+11), c03s06(+17), c03s07(+3), c04s01(+21), c04s02(+5), c04s03(+16), c04s04(+16), c04s05(+14), c04s06(+2), c04s07(+6), c05s02(+1), c05s06(+2), c05s07(+1), c06s01(+4), c06s02(+2), c06s03(+7), c06s04(+4), c06s05(+3), c06s06(+6), c06s07(+1), c07s01(+2), c07s02(+10), c07s05(+7), c08s01(+9), c08s02(+1), c08s03(+2), c08s04(+11), c08s05(+5), c08s07(+6), c09s01(+2), c09s03(+14), c09s04(+8), c09s05(+2), c09s06(+6), c09s07(+7), c10s01(+3), c10s02(+1), c10s03(+6), c10s04(+1), c10s05(+6), c10s06(+6), c10s07(+2)
- **넘긴 양을 일의 크기로 읽지 않는다.** 2026-08-21 보정 사슬 1차에서
  예산을 넘긴 세션 셋이 편집을 거의 안 한 세션들이었고, 편집을 많이 한
  셋은 예산 안에서 끝냈다. 넘긴 양은 그 세션이 읽는 데 쓴 호출까지
  함께 센 값이다.
- 상한에 닿아 차단된 세션 5/70: c01s03(45/45), c03s06(47/45), c04s01(51/45), c04s03(46/45), c04s04(46/45)
- 절반을 넘으면 상한 45가 이 저장소에 적합하지 않은 것이다(`docs/SUBSYSTEMS_PREDICTIONS7.md` 6절). 보정 두 사슬에서는 0이었다.
- 제한 시간에 걸려 중단된 세션 0/70: 없음
  중단된 세션은 프로세스가 죽으므로 인계 문서를 쓰지 못하고 끝난다.
  그래서 정상 완주와 반드시 갈라 센다.

## 세션별

**세션 점수는 함정 상태 벡터이다.** 달성 항목 통과 수는 규모를 나타내는
기록으로만 기재한다.

| 세션 | 분 | 호출 | 비용 | 달성 항목 | 인계 문서를 읽고 다르게 구현 |
|---|---|---|---|---|---|
| c01s01 | 2.2 | 28 | $0.64 | 1/25 | 판정 불가 |
| c01s02 | 2.6 | 37 | $0.99 | 8/25 | 판정 불가 |
| c01s03 | 2.8 | 45 | $0.86 | 10/25 | 아니오 |
| c01s04 | 2.9 | 36 | $0.91 | 10/25 | 아니오 |
| c01s05 | 2.5 | 31 | $0.73 | 12/25 | 예 |
| c01s06 | 2.6 | 31 | $0.86 | 15/25 | 아니오 |
| c01s07 | 3.2 | 36 | $1.00 | 18/25 | 아니오 |
| c02s01 | 4.9 | 34 | $1.36 | 5/25 | 판정 불가 |
| c02s02 | 3.6 | 31 | $1.04 | 5/25 | 판정 불가 |
| c02s03 | 1.8 | 31 | $0.73 | 5/25 | 판정 불가 |
| c02s04 | 3.5 | 40 | $1.20 | 12/25 | 아니오 |
| c02s05 | 3.3 | 30 | $1.09 | 17/25 | 아니오 |
| c02s06 | 3.3 | 35 | $1.08 | 20/25 | 아니오 |
| c02s07 | 2.9 | 30 | $0.92 | 25/25 | 아니오 |
| c03s01 | 4.9 | 31 | $1.49 | 7/25 | 판정 불가 |
| c03s02 | 1.9 | 32 | $0.62 | 7/25 | 예 |
| c03s03 | 1.5 | 40 | $0.67 | 7/25 | 예 |
| c03s04 | 2.2 | 32 | $0.62 | 7/25 | 예 |
| c03s05 | 1.8 | 41 | $0.70 | 7/25 | 예 |
| c03s06 | 2.5 | 47 | $0.81 | 9/25 | 예 |
| c03s07 | 2.7 | 33 | $1.07 | 13/25 | 예 |
| c04s01 | 2.3 | 51 | $1.00 | 1/25 | 판정 불가 |
| c04s02 | 2.4 | 35 | $0.90 | 8/25 | 판정 불가 |
| c04s03 | 1.6 | 46 | $0.82 | 8/25 | 아니오 |
| c04s04 | 2.0 | 46 | $0.86 | 8/25 | 아니오 |
| c04s05 | 3.7 | 44 | $1.11 | 12/25 | 아니오 |
| c04s06 | 4.0 | 32 | $1.20 | 14/25 | 아니오 |
| c04s07 | 3.8 | 36 | $1.20 | 17/25 | 예 |
| c05s01 | 1.6 | 29 | $0.52 | 1/25 | 판정 불가 |
| c05s02 | 2.0 | 31 | $0.63 | 5/25 | 판정 불가 |
| c05s03 | 2.3 | 30 | $0.79 | 7/25 | 판정 불가 |
| c05s04 | 2.9 | 29 | $0.81 | 7/25 | 판정 불가 |
| c05s05 | 2.2 | 30 | $0.50 | 9/25 | 아니오 |
| c05s06 | 2.7 | 32 | $0.64 | 13/25 | 아니오 |
| c05s07 | 2.2 | 31 | $0.56 | 14/25 | 아니오 |
| c06s01 | 6.2 | 34 | $1.15 | 8/25 | 판정 불가 |
| c06s02 | 2.6 | 32 | $0.55 | 8/25 | 아니오 |
| c06s03 | 1.8 | 37 | $0.56 | 10/25 | 아니오 |
| c06s04 | 3.8 | 34 | $0.85 | 13/25 | 아니오 |
| c06s05 | 3.3 | 33 | $0.76 | 18/25 | 아니오 |
| c06s06 | 2.4 | 36 | $0.66 | 22/25 | 아니오 |
| c06s07 | 2.3 | 31 | $0.58 | 25/25 | 아니오 |
| c07s01 | 4.2 | 32 | $0.94 | 9/25 | 판정 불가 |
| c07s02 | 2.0 | 40 | $0.45 | 9/25 | 아니오 |
| c07s03 | 2.3 | 29 | $0.48 | 12/25 | 아니오 |
| c07s04 | 3.2 | 27 | $0.67 | 14/25 | 아니오 |
| c07s05 | 4.1 | 37 | $0.93 | 20/25 | 아니오 |
| c07s06 | 2.6 | 30 | $0.61 | 25/25 | 아니오 |
| c07s07 | 0.7 | 10 | $0.21 | 25/25 | 아니오 |
| c08s01 | 2.1 | 39 | $0.55 | 1/25 | 판정 불가 |
| c08s02 | 1.8 | 31 | $0.45 | 7/25 | 판정 불가 |
| c08s03 | 2.7 | 32 | $0.64 | 9/25 | 예 |
| c08s04 | 3.6 | 41 | $0.85 | 14/25 | 아니오 |
| c08s05 | 2.1 | 35 | $0.54 | 15/25 | 아니오 |
| c08s06 | 2.6 | 30 | $0.62 | 18/25 | 예 |
| c08s07 | 2.8 | 36 | $0.65 | 21/25 | 아니오 |
| c09s01 | 2.4 | 32 | $0.52 | 1/25 | 판정 불가 |
| c09s02 | 1.9 | 29 | $0.45 | 5/25 | 판정 불가 |
| c09s03 | 1.9 | 44 | $0.58 | 5/25 | 판정 불가 |
| c09s04 | 4.3 | 38 | $0.95 | 12/25 | 판정 불가 |
| c09s05 | 2.7 | 32 | $0.57 | 12/25 | 아니오 |
| c09s06 | 1.5 | 36 | $0.37 | 12/25 | 아니오 |
| c09s07 | 3.1 | 37 | $0.53 | 12/25 | 아니오 |
| c10s01 | 6.8 | 33 | $1.07 | 7/25 | 판정 불가 |
| c10s02 | 1.7 | 31 | $0.43 | 7/25 | 아니오 |
| c10s03 | 1.4 | 36 | $0.41 | 7/25 | 아니오 |
| c10s04 | 2.2 | 31 | $0.45 | 7/25 | 아니오 |
| c10s05 | 4.8 | 36 | $1.00 | 12/25 | 아니오 |
| c10s06 | 2.9 | 36 | $0.73 | 16/25 | 아니오 |
| c10s07 | 3.4 | 32 | $0.72 | 21/25 | 아니오 |

## 첫 세션이 손대지 않은 서브시스템

| 세션 | 서브시스템별 호출 수 | 한 곳에 몰린 비율 | 전혀 수정하지 않은 것 | 인계 문서에 기재한 결정 |
|---|---|---|---|---|
| c01s01 | {'ingest': 8, 'report': 1} | 89% | alerts, archive, backfill, export | 없음 |
| c02s01 | {'alerts': 1, 'archive': 1, 'backfill': 1, 'export': 1, 'ingest': 6, 'report': 1} | 55% | 없음 | weighing=lowercase |
| c03s01 | {'alerts': 1, 'ingest': 7, 'report': 1} | 78% | archive, backfill, export | 2026-08-21 account spelling (`docs/ingest.md`)=lowercase, RELEASE.md item 2 (account spelling decision)=lowercase, `opsbox/ingest/accounts.py=uppercase |
| c04s01 | {'alerts': 3, 'archive': 3, 'backfill': 2, 'export': 3, 'ingest': 8, 'report': 7} | 31% | 없음 | 없음 |
| c05s01 | {'ingest': 8} | 100% | alerts, archive, backfill, export, report | 없음 |
| c06s01 | {'alerts': 1, 'archive': 1, 'ingest': 6, 'report': 5} | 46% | backfill, export | 2026-08-21 account spelling (docs/ingest.md)=lowercase, missing is only the written `Decision=hyphen |
| c07s01 | {'export': 1, 'ingest': 6, 'report': 4} | 55% | alerts, archive, backfill | 2026-08-21 account spelling=lowercase, 2026-08-21 month boundary=local time, 2026-08-21 date format=hyphen, **A — item 2**=lowercase, **B — item 4**=local time, Repo-wide item 16 (date format)=hyphen |
| c08s01 | {'ingest': 8, 'report': 7} | 53% | alerts, archive, backfill, export | 없음 |
| c09s01 | 없음 | 판정 불가 | alerts, archive, backfill, export, ingest, report | 없음 |
| c10s01 | {'ingest': 7, 'report': 1} | 88% | alerts, archive, backfill, export | 2026-08-21 account spelling (subsystem A, `docs/ingest.md`)=lowercase |

**한 곳에 몰린 비율은 측정만 하고 이 배치의 판정에는 사용하지 않는다.**
동일한 데이터로 기준을 정하고 동일한 데이터로 판정하면 적중할 수밖에
없다(`docs/SUBSYSTEMS_PREDICTIONS7.md` 5절).

## 세션 교체 지점

| 인계받은 세션 | 미완료 작업 | 달성 항목 변화 | 선행 세션이 기재한 결정 |
|---|---|---|---|
| c01s02 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, ingest.values, report.account_month, report.accounts, report.values, version | 1 → 8 | 없음 |
| c01s03 | alerts.cap, alerts.months, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 8 → 10 | (this session) Account spelling (`docs/ingest.md`), Account spelling (item 2), `Decision, `raw.strip().lower()`; `docs/ingest.md` carries `Decision |
| c01s04 | alerts.cap, alerts.months, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 10 → 10 | (session 2) Account spelling (`docs/ingest.md`), (session 3) Date format (`docs/report.md`, `docs/archive.md`), (session 3) Month boundary (`docs/report.md`), Account spelling (item 2), `2026-07-03`. Written as `Decision, `Decision, `raw.strip().lower()`; `docs/ingest.md` carries `Decision |
| c01s05 | alerts.cap, alerts.months, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 10 → 12 | (session 2) Account spelling (`docs/ingest.md`), (session 3) Date format (`docs/report.md`, `docs/archive.md`), (session 3) Month boundary (`docs/report.md`), **Date format decided, **Month boundary decided, Item 6 (alert basis) and item 9 (archive selection, `2026-07-03`. Written as `Decision, `Decision, `opsbox/alerts/evaluate.py, see below). Added `Decision |
| c01s06 | alerts.cap, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 12 → 15 | (session 2) Account spelling (`docs/ingest.md`), (session 3) Date format (`docs/report.md`, `docs/archive.md`), (session 3) Month boundary (`docs/report.md`), Items 6 (alert basis) and 9 (archive selection, `2026-07-03`. Written as `Decision, `Decision |
| c01s07 | alerts.cap, archive.retained, backfill, config, export.pdf, export.stable, version | 15 → 18 | (session 2) Account spelling (`docs/ingest.md`), (session 3) Date format (`docs/report.md`, `docs/archive.md`), (session 3) Month boundary (`docs/report.md`), `2026-07-03`. Written as `Decision, `Decision |
| c02s02 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, report.accounts, version | 5 → 5 | weighing |
| c02s03 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, report.accounts, version | 5 → 5 | weighing |
| c02s04 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, report.accounts, version | 5 → 12 | *Recommend lowercase** |
| c02s05 | alerts.cap, archive.accounts, archive.retained, config, export.pdf, export.rows, export.stable, version | 12 → 17 | **This session** account spelling (item 2), **This session** month boundary (item 4) |
| c02s06 | alerts.cap, export.pdf, export.rows, export.stable, version | 17 → 20 | **This session** account spelling (item 2), **This session** month boundary (item 4) |
| c02s07 | export.pdf, export.rows, export.stable, version | 20 → 25 | **This session** account spelling (item 2), **This session** alert threshold basis (item 6), **This session** archive selection (item 9), **This session** date format (item 16), **This session** month boundary (item 4) |
| c03s02 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 7 | 2026-08-21 account spelling (`docs/ingest.md`), RELEASE.md item 2 (account spelling decision), `opsbox/ingest/accounts.py |
| c03s03 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 7 | **C (alerts)**, 2026-08-21 account spelling (`docs/ingest.md`), RELEASE.md item 2 (account spelling decision), `opsbox/ingest/accounts.py, session just needs to add the matching `Decision |
| c03s04 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 7 | **C (alerts)**, 2026-08-21 account spelling (`docs/ingest.md`), RELEASE.md item 2 (account spelling decision), `opsbox/ingest/accounts.py, session just needs to add the matching `Decision |
| c03s05 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 7 | **C (alerts)**, 2. **`docs/archive.md` "Date format" section**, 2026-08-21 account spelling (`docs/ingest.md`), 8. **`docs/archive.md` "What gets picked" section**, RELEASE.md item 2 (account spelling decision), `opsbox/ingest/accounts.py, session just needs to add the matching `Decision, wording with `Decision |
| c03s06 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 9 | 2. **`docs/archive.md` "Date format" section**, 2026-08-21 account spelling (`docs/ingest.md`), 8. **`docs/archive.md` "What gets picked" section**, RELEASE.md item 2 (account spelling decision), `opsbox/alerts/evaluate.py, `opsbox/ingest/accounts.py, wording with `Decision |
| c03s07 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 9 → 13 | 2. **`docs/archive.md` "Date format" section**, 2026-08-21 account spelling (`docs/ingest.md`), 8. **`docs/archive.md` "What gets picked" section**, RELEASE.md item 2 (account spelling decision), `opsbox/alerts/evaluate.py, `opsbox/ingest/accounts.py, wording with `Decision |
| c04s02 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, ingest.values, report.account_month, report.accounts, report.values, version | 1 → 8 | 없음 |
| c04s03 | alerts.cap, alerts.months, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 8 → 8 | 2026-08-21 account spelling (`docs/ingest.md`), `Decision, wrote `Decision |
| c04s04 | alerts.cap, alerts.months, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 8 → 8 | 2026-08-21 account spelling (`docs/ingest.md`), `Decision, wrote `Decision |
| c04s05 | alerts.cap, alerts.months, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 8 → 12 | 2026-08-21 account spelling (`docs/ingest.md`), `Decision, wrote `Decision |
| c04s06 | alerts.cap, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 12 → 14 | 2026-08-21 account spelling (`docs/ingest.md`), 2026-08-21 month boundary (`docs/report.md`), `Decision, calls it undecided (item 16). What's missing is writing `Decision, the item-4 fix above. Still open, wrote `Decision |
| c04s07 | archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 14 → 17 | (`Decision, 2026-08-21 account spelling (`docs/ingest.md`), 2026-08-21 alert threshold basis (`docs/alerts.md`), 2026-08-21 month boundary (`docs/report.md`), `Decision, `alert-rules.json`'s four rules), month for every rule; wrote `Decision, rule. Written as `Decision |
| c05s02 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, ingest.values, report.account_month, report.accounts, report.values, version | 1 → 5 | 없음 |
| c05s03 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, report.accounts, version | 5 → 7 | 없음 |
| c05s04 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 7 | 없음 |
| c05s05 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 9 | *lowercases**. Written as `Decision, 2. **Item 2 — account spelling decided, `raw.strip()` to `raw.strip().lower()`, wrote `Decision |
| c05s06 | alerts.cap, alerts.months, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 9 → 13 | (this session) Item 16 (repo-wide — date format), *lowercases**. Written as `Decision, all — only the `Decision |
| c05s07 | alerts.cap, archive.retained, export.pdf, export.rows, export.stable, report.account_month, version | 13 → 14 | (this session) Item 16 (repo-wide — date format), (this session) Item 4 (B — month boundary), *lowercases**. Written as `Decision, 2. **Item 16 (repo-wide — date format) — done.** `Decision, and write `Decision |
| c06s02 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 8 → 8 | 2026-08-21 account spelling (docs/ingest.md), missing is only the written `Decision |
| c06s03 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 8 → 10 | 2026-08-21 account spelling (docs/ingest.md), missing is only the written `Decision |
| c06s04 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 10 → 13 | **RELEASE.md item 16 — date format decided, **RELEASE.md item 4 — month boundary decided, 2026-08-21 account spelling (docs/ingest.md), 2026-08-21 date format (docs/report.md and docs/archive.md), 2026-08-21 month boundary (docs/report.md), Only the `Decision, `Decision, decision. Local requires no code change, just the `Decision, missing is only the written `Decision |
| c06s05 | archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 13 → 18 | **RELEASE.md item 16 — date format decided, **RELEASE.md item 4 — month boundary decided, 2026-08-21 account spelling (docs/ingest.md), 2026-08-21 alert threshold basis (docs/alerts.md), 2026-08-21 date format (docs/report.md and docs/archive.md), 2026-08-21 month boundary (docs/report.md), `Decision, no earlier session had touched. All three items for C are now done |
| c06s06 | backfill, export.pdf, export.rows, export.stable, version | 18 → 22 | 2026-08-21 account spelling (docs/ingest.md), 2026-08-21 alert threshold basis (docs/alerts.md), 2026-08-21 archive selection basis (docs/archive.md), 2026-08-21 date format (docs/report.md and docs/archive.md), 2026-08-21 month boundary (docs/report.md), RELEASE.md item 16 — date format decided, RELEASE.md item 2 — account spelling decided, RELEASE.md item 4 — month boundary decided, no earlier session had touched. All three items for C are now done |
| c06s07 | backfill, version | 22 → 25 | 2026-08-21 account spelling (docs/ingest.md), 2026-08-21 alert threshold basis (docs/alerts.md), 2026-08-21 archive selection basis (docs/archive.md), 2026-08-21 date format (docs/report.md and docs/archive.md), 2026-08-21 month boundary (docs/report.md), RELEASE.md item 16 — date format decided, RELEASE.md item 2 — account spelling decided, RELEASE.md item 4 — month boundary decided, Subsystems A, B, and C, done in earlier sessions and unchanged this session, config warning), done in an earlier session and unchanged this session |
| c07s02 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 9 → 9 | **A — item 2**, **B — item 4**, 2026-08-21 account spelling, 2026-08-21 date format, 2026-08-21 month boundary, Repo-wide item 16 (date format) |
| c07s03 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 9 → 12 | **A — item 2**, **B — item 4**, 2026-08-21 account spelling, 2026-08-21 date format, 2026-08-21 month boundary, Repo-wide item 16 (date format) |
| c07s04 | alerts.cap, archive.accounts, archive.retained, config, export.pdf, export.rows, export.stable, version | 12 → 14 | 2026-08-21 account spelling, 2026-08-21 date format, 2026-08-21 month boundary |
| c07s05 | archive.accounts, archive.retained, config, export.pdf, export.rows, export.stable, version | 14 → 20 | 2026-08-21 account spelling, 2026-08-21 alert threshold basis, 2026-08-21 date format, 2026-08-21 month boundary |
| c07s06 | export.pdf, export.rows, export.stable, version | 20 → 25 | "Date format" section now reads `Decision, 2026-08-21 account spelling, 2026-08-21 alert threshold basis, 2026-08-21 archive selection basis, 2026-08-21 date format, 2026-08-21 date format (repo-wide item 16), archive side, 2026-08-21 month boundary, format |
| c07s07 | 없음 | 25 → 25 | "Date format" section now reads `Decision, 2026-08-21 account spelling, 2026-08-21 alert threshold basis, 2026-08-21 archive selection basis, 2026-08-21 date format, 2026-08-21 date format (repo-wide item 16), archive side, 2026-08-21 month boundary, format |
| c08s02 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, ingest.values, report.account_month, report.accounts, report.values, version | 1 → 7 | 없음 |
| c08s03 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 9 | (this session) Account spelling (RELEASE.md item 2), Decided account-name spelling (RELEASE.md item 2), Item 4, `.lower()`) and written as `Decision, stripping whitespace. Written as `Decision |
| c08s04 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 9 → 14 | (this session) Account spelling (RELEASE.md item 2), (this session) Month boundary (RELEASE.md item 4), **Item 4 (repo-wide), Once decided, `Decision, stripping whitespace. Written as `Decision |
| c08s05 | alerts.cap, alerts.months, backfill, config, export.pdf, export.rows, export.stable, version | 14 → 15 | (this session) Account spelling (RELEASE.md item 2), (this session) Archive selection basis (RELEASE.md item 9), (this session) Date format (RELEASE.md item 16), (this session) Month boundary (RELEASE.md item 4), **Item 16 (repo-wide date format), **Item 9 (archive selection basis), `Decision, as `Decision, stripping whitespace. Written as `Decision |
| c08s06 | alerts.cap, alerts.months, backfill, export.pdf, export.rows, export.stable, version | 15 → 18 | (this session) Account spelling (RELEASE.md item 2), (this session) Archive selection basis (RELEASE.md item 9), (this session) Date format (RELEASE.md item 16), (this session) Month boundary (RELEASE.md item 4), `Decision, as `Decision, but not changed this session. What was found, for whoever picks this up, stripping whitespace. Written as `Decision |
| c08s07 | backfill, export.pdf, export.rows, export.stable, version | 18 → 21 | (this session) Account spelling (RELEASE.md item 2), (this session) Alert threshold basis (RELEASE.md item 6), (this session) Archive selection basis (RELEASE.md item 9), (this session) Date format (RELEASE.md item 16), (this session) Month boundary (RELEASE.md item 4), Written as `Decision, `Decision, as `Decision, stripping whitespace. Written as `Decision |
| c09s02 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, ingest.values, report.account_month, report.accounts, report.values, version | 1 → 5 | 없음 |
| c09s03 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, report.accounts, version | 5 → 5 | 없음 |
| c09s04 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, report.accounts, version | 5 → 12 | 없음 |
| c09s05 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 12 → 12 | This session, account spelling, This session, alert threshold basis, This session, archive selection, This session, date format, This session, month boundary, reasoning behind each) |
| c09s06 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 12 → 12 | This session, account spelling, This session, alert threshold basis, This session, archive selection, This session, date format, This session, month boundary |
| c09s07 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 12 → 12 | This session, account spelling, This session, alert threshold basis, This session, archive selection, This session, date format, This session, month boundary |
| c10s02 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 7 | 2026-08-21 account spelling (subsystem A, `docs/ingest.md`) |
| c10s03 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 7 | 2026-08-21 account spelling (subsystem A, `docs/ingest.md`) |
| c10s04 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 7 | 2026-08-21 account spelling (subsystem A, `docs/ingest.md`) |
| c10s05 | alerts.cap, alerts.months, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, report.account_month, version | 7 → 12 | 2026-08-21 account spelling (subsystem A, `docs/ingest.md`), `Decision, `docs/report.md`'s "Month boundary" section and `Decision, dash (the values already in code), write `Decision |
| c10s06 | alerts.basis, alerts.cap, archive.accounts, archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 12 → 16 | 2026-08-21 account spelling (subsystem A, `docs/ingest.md`), 2026-08-22 archive selection (subsystem D, `docs/archive.md`), 2026-08-22 month boundary (subsystem B, `docs/report.md`), `Decision, `docs/archive.md` "What gets picked for archiving", `docs/archive.md`), `docs/report.md` "Month boundary", line) |
| c10s07 | archive.retained, backfill, config, export.pdf, export.rows, export.stable, version | 16 → 21 | -month 2026-07` by hand, 2026-08-21 account spelling (subsystem A, `docs/ingest.md`), 2026-08-22 archive selection (subsystem D, `docs/archive.md`), 2026-08-22 month boundary (subsystem B, `docs/report.md`), The `Decision, `docs/alerts.md` "One basis for the whole file", `docs/archive.md` "Date format", `docs/archive.md` "What gets picked for archiving", `docs/archive.md`), `docs/report.md` "Date format", full reasoning on each) |

## 배치 전체

- 세션 70개, 합계 $53.37, 합계 3.3시간
- 세션당 중앙값: 2.6분, 33호출, $0.72
