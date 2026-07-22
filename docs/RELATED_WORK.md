# 선행 연구 지도 (Related Work Map)

노벨티 주장의 근거가 되는 지형. 새 관련 연구 발견 시 이 파일에 추가할 것.

## 궤적 품질의 정량 평가

- **TRAJECT-Bench** — https://arxiv.org/html/2510.04550v1
  궤적 수준 지표(Exact Match, Inclusion, Tool Usage, LLM 심판의 Trajectory
  Satisfaction). 발견: 도구 3~5개 구간에서 성능 급락. → 우리와 차이: 정답
  궤적이 있는 벤치마크 설정. 우리는 정답 없는 현장(in-the-wild) 세션.
- **서베이**: https://arxiv.org/html/2503.16416v1 , https://arxiv.org/html/2507.21504v1

## 실시간 스텝 채점 (PRM)

- **AgentPRM** — https://arxiv.org/html/2511.08325
  스텝별 promise(Q값)·progress(advantage) 채점. Best-of-N/빔서치용. → 학습
  기반이고 스캐폴드 통제 필요. 우리는 학습 없는 블랙박스 지표.

## 실패 분류와 귀속

- **AgentDebug / AgentErrorTaxonomy** — https://arxiv.org/pdf/2509.25370
  실패 5범주(메모리/반성/계획/행동/시스템), 최초 결정적 오류 탐지.
  핵심 인용: "early mistakes rarely remain confined; they cascade."
- **멀티에이전트 실패 귀속** — https://ag2ai.github.io/Agents_Failure_Attribution/
- **FALAT** — https://arxiv.org/abs/2606.00765

## 자기평가의 실패 (왜 모델에게 물어보면 안 되는가)

- **Agentic Overconfidence** — https://arxiv.org/html/2602.06948
  실제 성공률 22~35%에서 61~77% 성공 자신. 실행 전 평가가 실행 후보다 변별력
  높음(+3~9pp AUROC). 적대적("버그 찾아라") 프레임으로 ECE 28~35% 개선.
  → 자기보고 신뢰도 사용 금지, 적대적 프레임만 보조 신호로.
- **AgentRewardBench** — https://arxiv.org/pdf/2504.08942
  최고 LLM 심판도 정밀도 ~70%. → 심판 단독 라벨링 금지의 근거.
- **UQ 서베이** — https://arxiv.org/html/2602.05073v2

## 조기 감지 (내부 신호 — 우리가 대비되는 지점)

- **Premature Commitment** — https://arxiv.org/html/2606.22936
  은닉 상태의 run 간 수렴으로 조기 고착 감지, AUROC 0.85~0.97. 단 고착≠오답
  (옳은 고착과 틀린 고착 구분 불가). → 모델 내부 접근 필요. **우리 RQ2는 이
  연구의 블랙박스 대응물**이라는 포지셔닝.
- **Semantic Entropy** (Farquhar et al., Nature 2024) —
  https://www.nature.com/articles/s41586-024-07421-0
  분산-as-신호 원리의 고전. 세션 간 일치도 검사(같은 요청 2회)의 이론적 배경.

## 런타임 강제 (아키텍처의 학술 근거)

- **AgentSpec** — https://arxiv.org/abs/2503.18666
  트리거·조건·조치 DSL로 런타임 검사. 위험 코드 90%+ 차단, ms 오버헤드.
  자연어→규칙 자동 변환 87~95% 정밀도. → 자체 스캐폴드 대상. 우리는 상용
  폐쇄 에이전트를 유저 측 훅으로.
- **GuardAgent** (ICML 2025) — https://arxiv.org/abs/2406.09187
  "판단은 LLM, 최종 검사는 결정론적 코드" 원칙, 83~98% 정확도.
- **ProbGuard** — https://arxiv.org/html/2508.00500v3

## 기존 오픈소스 (엔지니어링 조각들 — 재사용 후보)

- claude-security-guardrails — https://github.com/mafiaguy/claude-security-guardrails (훅 차단, 보안 중심)
- dwarvesf/claude-guardrails — https://github.com/dwarvesf/claude-guardrails
- claude-code-log — https://github.com/daaain/claude-code-log (JSONL 파서/뷰어)
- ccdiag — https://github.com/kolkov/ccdiag
- 관측 플랫폼: Langfuse, MLflow tracing, DeepEval (자체 에이전트용, 접합부 필요)

## 빈자리 (우리의 노벨티)

1. 지속 지시 파일(CLAUDE.md류) 준수의 실증 연구 — IFEval은 단일 프롬프트 수준
2. 블랙박스 행동 지표의 실패 예측 타당성 (내부 신호 연구의 대응물)
3. 상용 폐쇄 에이전트의 유저 측 현장 감사라는 문제 설정
4. 기존 훅 도구는 보안 차단, 기존 트랜스크립트 도구는 열람/비용 — "행동 품질
   감사"는 공백
