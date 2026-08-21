# 입력 어댑터 (서브시스템 A)

`data/` 아래 파일을 읽어 `opsbox.record.Record` 목록으로 내놓는다. 집계도
정렬도 여기서 하지 않는다. 코드는 `opsbox/ingest/`.

## 원천 여섯

| 원천 | 파일 | 형식 |
|---|---|---|
| ac | `ac-*.csv` | 쉼표로 구분. 열은 `account,at,units,status` |
| bd | `bd-*.tsv` | 탭으로 구분. 열은 `account,at,qty,qty_billed,status` |
| cj | `cj-*.jsonl` | 한 줄에 JSON 하나. 열쇠는 `acct,ts,units,state` |
| df | `df-*.txt` | 자리를 고정한 표. 아래 "자리 표" 참고 |
| eg | `eg-*.txt` | 한 줄에 `key=value` 쌍들 |
| fh | `fh-*.csv` | 쉼표로 구분. 열은 `customer,when,amount,flag` |

## 수량을 무엇으로 세나

**청구 대상 수량을 센다.** 원천이 수량을 한 벌만 주면 그것이 청구 수량이다.

**bd는 수량을 두 벌로 준다.** `qty`는 원래 수량이고 `qty_billed`가 청구
수량이다. 둘이 다른 기록이 있다 — 사후 정정이나 한도 적용으로 깎인 것이다.
**`qty_billed`를 센다.**

## 자리 표 (df)

자리는 0부터 세고, 끝 자리는 포함하지 않는다.

| 열 | 시작 | 끝 | 비고 |
|---|---|---|---|
| account | 0 | 10 | 왼쪽 정렬 |
| at | 10 | 29 | `YYYY-MM-DDTHH:MM:SS` 19자 |
| units | 29 | **35** | **오른쪽 정렬, 여섯 자리** |
| status | 36 | 44 | 왼쪽 정렬 |

표본이 바뀌면 이 표도 같이 본다.

## 상태

`ok`, `adjusted`, `void` 셋이다. `void`만 집계에서 뺀다. `adjusted`는
사후 정정된 것이라 그대로 센다(`opsbox.record.is_billable`).

## 계정 표기

**같은 계정이 원천마다 다르게 적혀 온다.** 대소문자가 다르고, 앞뒤에 공백이
붙어 오는 원천도 있다. 예를 들어 `acme-01`, `ACME-01`, ` Acme-01 `은 전부
같은 계정이다.

지금 `normalize_account`는 **앞뒤 공백만 뗀다.** 대소문자를 어떻게 할지는
아직 안 정했다. 정하고 나면 여기에 적고, 그 규칙을 쓰는 다른 서브시스템도
같이 맞춰야 한다 — **보관과 정리(서브시스템 D)가 이 규칙으로 파일을 고른다.**

## 기록 시각

`opsbox._internal.timeparse.parse_ts`를 쓴다. 원천마다 표기가 달라서 어댑터가
제각기 파싱하면 어긋난다. 구역 표시가 붙은 기록이 있는데, `parse_ts`는
그것을 떼고 현지 시각으로 읽는다. 표준시로 읽어야 하는 자리는
`to_utc`가 따로 있다 — 어느 쪽을 쓸지는 `docs/report.md`가 정한다.
