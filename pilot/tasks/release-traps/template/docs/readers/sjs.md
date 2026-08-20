# sjs

한 줄에 객체 하나(JSON Lines). 다른 원천과 달리 상태 필드 이름이
`status`가 아니라 `state`다.

```
account, at, units, state
```

`state`가 `adjusted`인 기록은 **정정 후 값**이다. 원천이 원본을 다시 보내지
않으므로 그대로 쓰면 된다.
