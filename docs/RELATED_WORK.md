# 선행 연구 지도 (Related Work Map)

노벨티 주장의 근거가 되는 지형. 새 관련 연구 발견 시 이 파일에 추가할 것.

## Run-to-run / 세션 간 변동성 (본 연구의 핵심 지형; 2026-07 딥서베이, 주장별 3표 적대 검증)

### 현상 — 결과 수준의 실증 (분산이 존재한다는 것까지는 기존 연구가 확립)

- **Ouyang et al.** (ACM TOSEM) — https://arxiv.org/abs/2308.02828
  단발 코드 생성의 비결정성: 829문제에서 반복 요청 간 테스트 출력이 한 쌍도
  일치하지 않는 과제 비율 75.76%(CodeContests)/51.00%(APPS)/47.56%(HumanEval).
  temp=0으로도 제거 안 됨. 주의: 헤드라인 수치는 temp=1, GPT-3.5 시대.
  → 단발 생성·출력 수준. 궤적/도구 사용 없음.
- **τ-bench** (Yao et al., ICLR 2025) — https://arxiv.org/abs/2406.12045
  pass^k(k회 전부 성공) 도입: GPT-4o pass^1 ~61% → pass^8 <25% (retail).
  일관성을 공개 문제로 명명. 주의: 확률적 유저 시뮬레이터가 분산에 섞임.
  → 결과 수준 스칼라만. 실패 분석도 1회 시행 기준 — 궤적 분기 분석 없음.
- **AI Agents That Matter** (Kapoor et al., NeurIPS 2024) — https://arxiv.org/abs/2407.01502
  발표된 에이전트 점수가 자체 재현 5회의 최대값보다 높은 사례 다수; error
  bar 부재 관행 비판, 5회 반복 + 95% CI를 교정 관행으로 제시.
- **Beyond pass@1** (Khanal et al., 2026 preprint) — https://arxiv.org/pdf/2603.29231
  23,392 에피소드(오픈웨이트 10종, k=3): pass@1 76.3%→52.1% (과제 길이에 따라
  전 모델 하락). VAF(분산 증폭 계수)가 능력 상위 4종에서 2.37~2.60 — **높은
  run 간 분산은 불안정이 아니라 능력의 신호** (2-1 검증; Bernoulli 바닥 효과
  일부). 도구 호출 엔트로피 기반 MOP(붕괴 시작점) 궤적 지표 도입, 사전 예측은
  future work로 제안만. → 우리 RQ2의 선점 아님(실행 안 됨). 프리프린트 주의.
- **AI21: 200k SWE-bench runs** — https://www.ai21.com/blog/scaling-agentic-evaluation-swe-bench/
  산업 규모 방증: 인스턴스당 4~16 시드 반복(duplicity)이 필수라는 운영 결론.
- **On Randomness in Agentic Evals** (Bjarnason et al., KTH; ICLR 2026 W
  Agents in the Wild) — https://arxiv.org/abs/2602.07150
  SWE-bench Verified **60,000 궤적**(3모델×2스캐폴드×10반복): 단일 실행
  선택에 따라 pass@1 ±2.2~6.0%p, temp0에서도 σ>1.5%p; **궤적은 전체
  토큰의 첫 몇 % 안에서 갈라지고 작은 차이가 다른 해결 전략으로 증폭**.
  Zenodo에 7.7GB 궤적 공개(record 18684664) — 우리 지표의 외부 데이터
  교차 검증 후보. → 배경 절의 핵심 인용. 단, 목적은 평가 점수의 통계적
  신뢰성(반복을 늘려라)이지 단일 실행의 조기 판별이 아님 — 우리와의 경계.
- **Zhou et al.** (2026 preprint) — https://arxiv.org/abs/2606.00920
  16모델×100문제×5반복: run-level pass rate가 retry-free coverage를 최대
  **17.8%p 과대평가**, 유사 모델 간 순위 역전. "평균적으로 푼다"와 "한
  번에 안정적으로 푼다"의 분리 근거 — 결과 보고 시 지표 구분 인용용.

### 원인 — 서빙 스택 비결정성 (유저가 통제할 수 없음 = 우리 설정의 전제)

- **Defeating Nondeterminism** (He et al., Thinking Machines, 2025) —
  https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
  temp0에서 1000회 중 80개 상이 완성(Qwen3-235B). 주범은 커널의 배치 불변성
  부재 + 서버 부하(배치 크기)의 비결정적 변동 — "동시성+원자연산" 통념 반박.
  batch-invariant 커널로 완전 결정론(1.6~2.1x 감속). SGLang/vLLM이 재현·채택.
- **Yuan et al. 2025** — https://arxiv.org/abs/2506.09501
  greedy에서도 배치 크기/GPU 수/GPU 종류만으로 출력 변화; BF16에서 정확도
  최대 9% 변동. **주의(검증에서 0-3 반박됨):** "FP 반올림 캐스케이드가 근본
  원인"이라고 쓰면 틀림 — 정확한 서술은 FP 비결합성=가능 조건, 배치
  비불변+부하 변동=트리거.
- **Atil et al.** (Eval4NLP 2025) — https://arxiv.org/abs/2408.04667
  temp0·고정 시드에도 10run 정확도 최대 15% 변동; best/worst envelope 70%
  (관측된 두 run 간 격차가 아니라 문항별 any/all 포락선 — 인용 시 구분).
- FP 비결합성 기초: Shanmugavelu et al., SC'24 W — https://arxiv.org/abs/2408.05148
- → 함의: 서버측 교정(batch-invariant 등)은 폐쇄 상용 에이전트의 유저에게
  불가능. 변동성은 주어진 조건이고, 우리는 그것의 **행동 수준 특성화·예측**을 한다.

### 궤적 수준 특성화 (노벨티 인접 지대 — 반드시 인용·차별화)

- **How Consistent Are LLM Agents?** (Yagubyan, 2026-05 preprint) —
  https://arxiv.org/abs/2605.28840 — **가장 가까운 선행 연구.**
  1,140 트레이스(19과제×10run×6모델): 도구 순서 유사도(TSS) 0.87 vs 인자
  일관성 0.69; **행동 분기의 60%가 첫 두 도구 호출에서 발생**(평균 분기점
  2.2스텝); TSS 상위 조건 정답률 90.2% vs 하위 61.2% (d=0.81) — 인자 분산은
  무관(r=0.12 n.s.). 차별점 3개를 명시할 것: (a) 결정론적 모의 도구
  파이프라인 — 실제 코드베이스의 코딩 에이전트 아님, (b) 완주한 N개 run의
  사후·조건 수준 상관 — 진행 중 세션의 조기 예측 아님, (c) 지시 준수·탐색
  깊이 차원 없음. 단일 저자 비심사 프리프린트 — 투고 전 재확인.
- **When Agents Disagree With Themselves** — https://arxiv.org/html/2602.11619v1
  반복 run에서 도구 호출 스키마(안정) vs 인자(가변) 분리; 최종 NL 응답은
  도구 시퀀스가 같아도 <5% 일치.
- **What Resolve Rate Hides** — https://arxiv.org/pdf/2607.06184
  코딩 에이전트의 resolve rate가 숨기는 궤적 구조 진단 — 단 교차 과제 구조,
  동일 과제 반복 분기 아님 (확인 필요로 남김).
- **Canonical Path Deviation** — https://arxiv.org/pdf/2602.19008
  model×task 쌍의 22.5%가 반복 run에서 혼합 결과; 정준 해결 경로 이탈을
  within-task 비일관성의 기제로 제시 (사후 인과 분석, 온라인 예측 아님).
- **Understanding Code Agent Behaviour** (Majgaonkar et al., ICSE 2026
  manuscript) — https://arxiv.org/pdf/2511.00197
  성공/실패 궤적 대비. **주의할 각도: 실패 실행의 72~81%도 문제 파일은
  찾았다** — 위치 탐색(coverage류)만으로 성패를 설명 못 하고 수정의
  품질이 관건. 우리 coverage 신호의 한계 예고; 보정에서 coverage-성패
  관계를 실측할 것.
- **Confident and Wrong: Silent Semantic Failures** (Mehta, 2026 preprint)
  — https://arxiv.org/abs/2603.25764
  SWE-bench 1,750 궤적(50과제×4모델×5회): 과제별 결과가 **극단적 쌍봉**
  (5회 전부 성공 아니면 전부 실패) — 일관성은 옳은 해석뿐 아니라 **잘못된
  해석도 증폭**한다(실패 run의 68%[GPT-5]~80%[Llama 4]가 동일 오해석 반복;
  ChatGPT 정리본의 "71%"는 날조 수치). pre-edit 가드 프롬프트는 resolve
  개선 실패. → 두 함의: (1) 궤적 일관성↔성공 상관(2605.28840)을 액면
  수용 금지 — 일관성은 확신의 신호이지 정답의 신호가 아님, (2) 쌍봉
  주장은 우리 within-task 분산 설계와 긴장 — 우리 보정에서 C 과제가 1/3
  혼합 결과를 낸 것은 우리 과제가 쌍봉을 벗어나는 변별력을 가진다는 초기
  반례. 본 수집에서 과제별 성공 분포의 쌍봉성 자체를 보고할 것.
- **Entropy-Based Observability** — https://arxiv.org/pdf/2606.05872
  궤적 엔트로피 지표 제안(반복 실행 설정 명시) — 지표 제안이지 실증 아님.

### 변동성의 이용·예측 (우리 RQ2의 경쟁 지형)

- **Doomed from the Start** (Ruan et al., 2026) — https://arxiv.org/abs/2607.06503
  첫 상호작용 라운드에서 실패 예측·조기 중단(recall 90%에서 토큰 54~60%
  절감). 단 **내부 활성값 선형 프로브(화이트박스)** 이고 행동-신호-만
  모니터링을 약한 베이스라인으로 보고. → 우리 RQ2는 이 논문이 약하다고 치부한
  블랙박스 체제에서의 도전이자, 폐쇄 상용 에이전트에는 유일하게 가능한 체제.
- **AgentForesight** — https://arxiv.org/abs/2605.08715
  prefix만 보고 계속/경보를 결정하는 온라인 감사 프레이밍(우리와 동형) — 단
  RL로 학습한 7B 감사자, 멀티에이전트 대상. 결정론적 엔진 아님.
- **LLM-as-a-Verifier** — https://arxiv.org/abs/2607.05391
  SWE-bench 롤아웃 N=16 사후 선택(+7.9%p) — 전부 완주 후 선택, 조기 아님.
- **Selective Rollout** — https://arxiv.org/pdf/2605.05802
  롤아웃 간 prefix edit distance로 중도 종료 — RL 학습 비용 절감 문맥.
  100그룹×8롤아웃 중 39%는 분산 0 (mixed 61%).
- **MoE routing (RAD)** — https://arxiv.org/abs/2606.22798
  라우팅 상태로 롤아웃 선택 — 화이트박스 MoE 한정, 사후 선택.

### 지시 준수·절차 평가 (준수 차원의 이웃 — 2026-07-23 검증 추가)

- **AgentIF** (Qi et al., NeurIPS 2025 D&B Spotlight) —
  https://arxiv.org/abs/2505.16944
  에이전트 시나리오 지시 준수 벤치마크: 실제 앱 50개에서 707개 지시(평균
  1,723단어, 평균 11.9개 제약), 제약별 code/LLM/hybrid 평가기. 프런티어
  모델도 조건부 제약·도구 명세에서 낮은 성능. → **단발 지시-응답 평가**
  — 지속 파일(CLAUDE.md류)·세션 관통·세션 간 준수 분산은 다루지 않음
  (검증 확인). 빈자리 3의 문구를 이 논문 기준으로 정교화.
- **PAE: corrupt success** (Cao et al., 2026 preprint) —
  https://arxiv.org/abs/2603.03116
  τ-bench에서 성공 판정의 **27~78%가 절차 위반을 숨긴 "corrupt success"**;
  Utility/Efficiency/Interaction/Procedural Integrity 4축 분리. 인용 주의:
  judge 정밀도는 93.8~95.2% (사람 검증 131건 후). → "테스트는 통과했지만
  규칙은 어긴 세션"이라는 우리 측정 대상의 학술적 선례·명명.
- **InferAct** (Fang et al., EMNLP 2025) — https://arxiv.org/abs/2407.11843
  critical action 실행 전 LLM 판단기로 의도 오정렬 탐지(Macro-F1 최대
  +20%). → 우리 PreToolUse 훅의 확률적 대응물: LLM 가드 vs 결정론 규칙
  가드의 비교 프레임에서 베이스라인 인용.
- **FixedBench** (Gloaguen et al., 2026 preprint) —
  https://arxiv.org/abs/2605.07769
  수정 불필요 과제 200개에서 프런티어 모델의 **35~65%가 불필요 수정**
  (action bias); "수정 전 재현" 지시는 편향을 줄이나 over-abstention 유발
  — 프롬프트 수준 규칙의 부작용 실증(우리 "강제는 코드로" 원칙의 방증).
  → 본 실험의 negative task arm 후보.
- **Instruction Adherence in Coding Agent Configuration Files** (McMillan,
  2026-05 preprint; G3 노벨티 워치에서 발견·초록 검증) —
  https://arxiv.org/abs/2605.10039
  **CLAUDE.md류 지속 파일 준수의 최초 대규모 실증** — 빈자리 3의 "완전
  공백" 문구를 무효화하는 논문. Claude Code CLI 1,650세션(주로 Sonnet
  4.6 — 우리 본 수집과 동일 모델), 파일 구조 변수 4종(크기/위치/구조/
  인접 파일 모순) 요인 설계 → 구조 변수는 전부 효과 없음, 지배 패턴은
  **세션 내 감쇠**(생성 함수 1개당 준수 odds -5.6%). → 경계: 준수율의
  **세션 간 분산**, 궤적 일관성과의 공분산, 행동 궤적 지표는 없음(단발
  주석 준수만). 우리 H1b의 "길이에 따라 확대" 부분은 이 논문의 세션 내
  감쇠와 겹침 — 세션 간 축으로 재정위하고 인용할 것.
- **How Coding Agents Fail Their Users** (Tang et al., 2026-05 preprint;
  G3 노벨티 워치에서 발견·초록 검증) — https://arxiv.org/abs/2605.29442
  실사용 20,574세션(1,639 레포, IDE+CLI)의 관찰 연구: 개발자 반발
  (pushback)로 드러난 오정렬 7형 분류 — **rule-following이 실패 형태로
  실증**됨(91.5%가 명시적 유저 교정 필요). → 반복 실행·세션 간 분산·조기
  예측 없음(관찰·분류). "규칙 위반은 실사용에서 실제 비용"이라는 동기
  절 인용용.

### 보고 관행 비판·방법론 준거

- **Adding Error Bars to Evals** (Miller, Anthropic 2024) — https://arxiv.org/abs/2411.00640
- **Questionable Practices in ML** (Leech et al. 2024) — https://arxiv.org/pdf/2407.12220
- **Lessons from the Trenches** (Biderman et al. 2024) — https://arxiv.org/html/2405.14782
- **Guidelines for Empirical Studies in SE involving LLMs** (Baltes et al.,
  EMSE 게재 확정, 22인 공저) — https://arxiv.org/abs/2508.15503
  연구 유형 7종·설계/보고 지침 8개 + 통합 체크리스트(llm-guidelines.org).
  **"context files 등 구성 메커니즘 보고 must, 구성 아티팩트 공개 should",
  노출 도구/MCP 명시 must, 세션 런타임 트레이스 공개, 반복 횟수 정당화
  (power analysis 등)** — 우리 보고 프로토콜의 준거 문헌. 인용 주의:
  CLAUDE.md를 명시적으로 지칭하지는 않음("context files"라는 일반 표현).

### 서베이가 남긴 열린 확인 사항

1. ICSE/FSE/ICLR 2026 워크숍에 SWE-bench류 코딩 에이전트의 mid-run 성공 예측
   동시 연구가 있는지 투고 전 표적 검색 (노벨티 최대 잔여 리스크)
2. 서빙 비결정성을 통제(온도 0 + batch-invariant)했을 때 에이전트 루프의
   경로 의존성이 분산의 몇 %를 설명하는지 분해한 연구는 없음 — 우리가 논의
   가능한 공백
3. 모의 파이프라인의 "60% 초반 분기"가 실제 코딩 에이전트에서 재현되는가
4. **지시 준수와 궤적 일관성의 공분산(규칙 어기는 run이 곧 행동 이탈 run인가)
   은 어떤 선행 연구도 다루지 않음 — 우리 고유 측정 지점**

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

## 빈자리 (우리의 노벨티 — 2026-07 딥서베이 후 재정의)

노벨티는 "분산이 존재한다"가 아니다(확립됨). 다음 조합이 공백이다:

1. **실제 코드베이스 위 실제 코딩 에이전트**의 동일 과제 반복 세션에서 행동
   궤적 분기를 특성화 — 가장 가까운 2605.28840은 모의 도구 파이프라인,
   2603.29231은 예측을 future work로만 제안
2. **진행 중 세션의 조기(within-run) 성패 예측을 블랙박스 행동 신호만으로**
   — 2607.06503은 내부 활성값 프로브(화이트박스)로 하고 행동 신호를 약한
   베이스라인 취급; 폐쇄 상용 에이전트에는 블랙박스가 유일 가능 체제
3. ~~지속 지시 파일(CLAUDE.md류) 준수의 실증 연구~~ **(2026-07-24 축소:
   2605.10039가 CLAUDE.md 준수 실증을 선점** — 단발 주석 준수 + 세션 내
   감쇠까지). 남은 공백: **준수율의 세션 간 분산, 궤적 일관성과의 공분산,
   행동 규칙(도구 사용 절차) 준수** — 2605.10039는 코드 주석 삽입 규칙만,
   AgentIF(2505.16944)는 단발 평가, corrupt success(2603.03116)는
   절차-성공 분리까지만
4. 상용 폐쇄 에이전트의 유저 측 현장 감사라는 문제 설정 (기존 훅 도구는
   보안 차단, 트랜스크립트 도구는 열람/비용 — "행동 품질 감사"는 공백)

주의: 1·2의 최근접 논문 두 편(2605.28840, 2603.29231)은 모두 2026년 비심사
프리프린트 — 투고 직전에 개정판/심사 통과 여부와 동시 연구를 재확인할 것.
