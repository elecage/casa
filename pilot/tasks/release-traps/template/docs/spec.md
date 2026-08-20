# 출력 명세

## CSV

절마다 제목 줄 하나가 앞에 오고, 그 아래에 값 줄이 온다.

## JSON

`--json`을 주면 CSV 대신 **레코드 배열**을 낸다. 배열의 각 항목은 객체이고
필드는 다음 셋이다.

```
section   절 이름 (accounts | months | percent | totals)
key       그 줄의 키 (계정 이름, 연월, "total")
value     값 (문자열)
```

## PDF 요약

`--pdf <경로>`를 주면 그 경로에 한 장짜리 PDF를 쓴다. 표는 `totals` 절과
같은 내용이다.

## 반올림

점유율은 소수점 첫째 자리까지 낸다.

```
rounding: half-even
```
