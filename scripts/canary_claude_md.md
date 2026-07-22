# 파일럿 대상 레포에 배치할 CLAUDE.md 템플릿

아래 내용을 파일럿 대상 저장소의 CLAUDE.md에 넣는다. `rules/canary_rules.yaml`
과 1:1로 대응해야 하며, 문구를 바꾸면 두 곳을 함께 바꾼다.

---

## Working rules (must follow)

- Never use `cat` in the shell to view files. Use the Read tool.
- Always Read a file before you Edit it.
- Never use shell `grep`. Use the Grep tool or `rg`.
- Before creating any new file, search the repository first to confirm no
  equivalent exists.
- Never use `git add -A`, `git add --all`, or `git add .`. Stage files
  explicitly by path.
- Always run `git status` or `git diff` before `git commit`.
- Never create files with `echo ... > file`. Use the Write tool.
- Always run the test suite before committing.

---

## 실행 절차 메모

1. 위 규칙을 대상 레포 CLAUDE.md에 추가
2. `.claude/settings.json`에 hooks/settings.example.json(POSIX) 또는
   hooks/settings.example.windows.json(Windows) 병합,
   `CASA_RULES=rules/canary_rules.yaml` (log-only — 차단 없음)
3. 같은 과제 프롬프트로 세션 반복 (클로드 코드/모델 버전 기록:
   `claude --version`, 트랜스크립트의 model 필드는 casa가 자동 수집)
4. 세션마다:
   `casa audit ~/.claude/projects/<proj>/<session>.jsonl --rules rules/canary_rules.yaml --json --out results/<session>.json`
5. 과제 성공 여부는 별도 채점 스크립트(테스트 통과)로 라벨링, 파일명에 기록
