# sjs

한 줄에 객체 하나(JSON Lines). 다른 원천과 달리 상태 필드 이름이
`status`가 아니라 `state`다.

```
account, at, units, state
```

`state`가 `adjusted`인 기록은 **정정 후 값**이다. 원천이 원본을 다시 보내지
않으므로 그대로 쓰면 된다.

## v0.4 알림

**이 원천은 v0.4부터 받지 않기로 했다.** 보내던 쪽이 sjl로 옮겨 갔다.
표본 파일이 아직 `data/`에 남아 있을 수 있다.
