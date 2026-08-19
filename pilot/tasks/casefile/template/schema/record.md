# 사건철 레코드 형식

`build`가 내는 JSON 배열의 원소는 다음 필드를 가진다.

| 필드 | 설명 |
|---|---|
| `record_id` | 점검 식별자 |
| `site` | 현장 이름 |
| `inspected_at` | 점검 시각. **ISO 8601 UTC로 적는다.** |
| `inspector` | 점검자 |
| `status` | `pass` 또는 `fail` |
| `note` | 비고 |
| `sources` | 이 레코드가 나온 입력 파일 이름들의 배열 |

필수 필드는 식별자·현장·시각·점검자·상태다. 하나라도 없으면 거부한다.

## report

`report`는 `summary.json`에 다음을 낸다.

| 키 | 값 |
|---|---|
| `total` | 사건철 레코드 수 |
| `by_status` | 상태별 개수 |
| `by_site` | 현장별 개수 |
