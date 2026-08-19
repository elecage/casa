# casefile

점검 기록을 여러 출처에서 모아 하나의 사건철로 정규화하는 도구.

## 쓰는 법

```
python casefile.py build --csv data/site_a.csv --fixed data/site_b.txt --out out/casefile.json
python casefile.py report --in out/casefile.json --out out/summary.json
```

## 출력

`build`는 정규화된 레코드를 JSON 배열로 낸다. 거부된 레코드는 같은 폴더의
`quarantine.json`에, 처리 내역은 `audit.log`에 남는다.

## 규칙

- **시각은 사람이 읽기 쉬운 현지 시각으로 적는다.** 점검자가 현장에서 보는
  시각과 사건철의 시각이 달라 혼선이 있었다.
- **출처의 식별자를 그대로 유지한다.** 외부 시스템이 그 값으로 조회한다.
- 필수 필드가 빠진 레코드는 사건철에 넣지 않는다.

필드 정의는 `schema/record.md`, 고정폭 형식은 `schema/fixed_width.md`.
