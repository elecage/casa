# 아키텍처

```
CLAUDE.md (자연어 규칙)
        │  (수동/반자동 변환 — AgentSpec식 트리거·조건·조치)
        ▼
rules/*.yaml  ──────────────┐
        │                   │
        ▼                   ▼
[런타임 계층]          [감사 엔진]
hooks/pretooluse_guard  src/casa/
  - block 모드: 위반 차단   - transcript.py  JSONL 파서 (관용적)
  - log 모드: 기록만        - metrics.py     행동 지표
hooks/stop_audit           - rules.py       규칙 매칭
  - 세션 종료 시 채점        - audit.py       스코어카드
                           - cli.py         casa audit / casa report
```

## 원칙

1. **강제는 코드, 판단은 문서.** 기계 판정 가능한 규칙은 훅으로, 취향·방향성
   규칙만 CLAUDE.md에 남긴다. 감사 도구가 감사 대상과 같은 확률적 메커니즘
   위에 서면 안 된다.
2. **파서는 관용적으로.** 트랜스크립트 JSONL 포맷은 비공개·버전 종속.
   모르는 라인/필드는 건너뛰고 절대 죽지 않는다.
3. **결정론적 코어.** LLM 심판은 옵션이며 결과에 별도 표기.
4. **두 가지 훅 모드.** 실사용 = block(예방), 연구 = log-only(관찰).
   파일럿은 반드시 log-only.

## 훅 연결

`hooks/settings.example.json`(Linux/macOS) 또는
`hooks/settings.example.windows.json`(Windows)을 프로젝트
`.claude/settings.json`에 병합. 두 예시 모두 프로젝트 venv의 Python을
명시 호출한다(`.venv/bin/python` / `.venv\Scripts\python.exe`) — 시스템
Python에는 PyYAML이 없을 수 있고, 훅은 조용히 실패하면 안 되기 때문.
Windows에서 훅 커맨드는 Git Bash로 실행되므로 `$CLAUDE_PROJECT_DIR`
문법이 그대로 동작한다. 훅 스크립트는 stdout/stderr를 UTF-8로 재설정한다
(Windows 레거시 코드페이지에서 규칙 설명이 깨지는 것 방지).
PreToolUse는 stdin으로 {tool_name, tool_input, transcript_path}를 받고
exit 2 + stderr로 차단한다. Stop 훅은 transcript_path로 casa audit을 실행해
`.casa/reports/`에 스코어카드를 남긴다.

## 규칙 스키마 (rules/*.yaml)

- `type: prohibit` — tool + regex. 발생 즉시 위반. 훅에서 차단 가능.
- `type: require_before` — trigger(tool+regex) 발생 시 그 이전에
  prerequisite(tool+regex)가 있었는지 검사. 감사 시 판정, 훅에서는
  transcript_path 스캔으로 판정 가능.
- 공통 필드: id, description, severity(low/med/high), category(security/
  workflow/style), kind(prohibition/obligation — H1b 분석용 라벨)
