# sjl

한 줄에 객체 하나(JSON Lines). 필드는 `account`, `at`, `units`, `status`.

기록 시각은 구역 표시가 붙어 온다(`2026-07-02T08:00:00Z`).

`status`가 `adjusted`인 기록은 **사후 정정된 값**이며 집계에 들어간다.
