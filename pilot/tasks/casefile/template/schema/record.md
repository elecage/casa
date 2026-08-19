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

## quarantine

거부된 레코드는 `quarantine.json`에 배열로 남긴다. 각 원소는 최소한 다음을
가진다.

| 필드 | 설명 |
|---|---|
| `record_id` | 거부된 레코드의 식별자 |
| `site` | 현장 이름 |
| `source` | 어느 입력 파일에서 왔는지 |
| `reason` | 왜 거부됐는지 |

## report

`report`는 `summary.json`에 다음을 낸다.

| 키 | 값 |
|---|---|
| `total` | 사건철 레코드 수 |
| `by_status` | 상태별 개수 |
| `by_site` | 현장별 개수 |

## build 옵션

| 옵션 | 뜻 |
|---|---|
| `--append` | 기존 사건철 파일에 새 입력을 합친다. 기존 레코드는 보존한다 |
| `--since` / `--until` | 점검 시각이 그 범위 밖인 레코드를 제외한다 |
| `--split-by-site` | 현장별로 파일을 나눠 그 디렉토리에 낸다 (`<현장>.json`) |

## conflicts

같은 사건인데 값이 다른 중복은 `conflicts.json`에 배열로 남긴다. 각 원소는
최소한 식별자, 현장, 어긋난 필드 이름을 가진다.
