# usagectl

여러 원천 시스템의 사용량 기록을 모아 월간 리포트를 만든다. 표준 라이브러리만
쓴다.

```
python -m usagectl.cli --config config.sample.json --out report.csv
```

## 원천 어댑터

원천마다 어댑터 모듈이 하나씩 있다(`usagectl/readers/`). 새 원천을 붙이려면
모듈을 하나 더하고 `REGISTRY`에 등록한다. 어댑터별 입력 형식은
`docs/readers/` 아래에 한 장씩 있다.

## 리포트 절

절도 모듈 하나씩이다(`usagectl/reports/`). `--section`으로 고를 수 있고,
지정하지 않으면 전부 낸다.

## 한계

한 번에 최대 1000행까지 처리한다. 그보다 큰 입력은 나눠서 돌린다.
