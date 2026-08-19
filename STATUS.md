# STATUS — 세션 인수인계 파일

새 세션은 CLAUDE.md 필독 문서 다음에 이 파일을 읽는다. 작업 상태가 바뀌면
**같은 커밋에서** 이 파일을 갱신한다. 규칙은 CLAUDE.md의 "Session handoff" 절.

## 다음 세션 시작점

**→ W14: ML arm `ml-shift` sonnet 보정 완료(2/3). 다음 할 일 = 힌트
제거판 n=3 프로브 → 그 결과로 본 수집 조건 확정.**

**힌트 제거판 `tabular-b` 제작 완료 (2026-08-19).**
`pilot/tasks/tabular-b/` — 데이터·오라클·τ(0.73)·레퍼런스·naive 전부
`ml-shift`와 **바이트 동일**(테스트로 고정), **차이는 문구뿐**: 저장소명
중립화, prompt·template README·solution 독스트링의 "optimise for
generalisation"/CV 경고 문장 삭제, pyproject description 중립화. 남긴 것 =
"채점은 held-out AUROC + 임계"(채점 절차 사실은 알려야 gotcha가 아님).
함정(`s`)은 이제 train/test 분포 비교로만 발견 가능. 세션이 보는 표면에
힌트 단어가 다시 들어오면 `tests/test_tabular_b_task.py`가 깨진다(ml-shift
표면에는 실제로 걸림 = 비공허 검사 확인).

**다음 명령 (프로브):** `.venv\Scripts\python.exe pilot/run_sessions.py
pilot/tasks/tabular-b -n 3 --model sonnet --out results/cal/tabular-b`
(~$1.6, ~20분).
판정(선등록): 성공률이 눈에 띄게 떨어지면 중립판을 본 수집 조건으로 채택
(+"힌트 한 문장이 달성을 가른다"를 발견으로 보고), 거의 같으면 현행
`ml-shift` 유지하고 힌트 논란은 이 기록으로 방어. **그 다음** 본 수집
sonnet n=30 (≈$16, 사용 한도 때문에 분할), haiku 대조는 그 후 판단.

**보정 결과 (2026-07-25 18:05~18:20, sonnet, `results/cal/ml-shift`, 미기록
분 소급 기재 2026-08-19):** 2/3 통과. held-out AUROC = **0.6423(실패, `s`
포함: 로지스틱+GB 앙상블, s 계수 ~5.6) / 0.7973 / 0.7973(둘 다 `s` 제거,
x1~x3만)**, τ=0.73. 세션당 249~343초·$0.43~0.60, 위반 0, 픽스처 무수정,
숨은 라벨 접근 0, `pytest_exit=0` 전건(보이는 테스트는 순진해도 통과 —
설계대로).

**의미 (이 arm의 존재 이유 충족):** **같은 조건에서 성공·실패가 둘 다 나온
첫 과제.** 지금까지는 조건별 achievement가 거의 결정론적이었다(F1:
schedule-haiku 28/30 동일, ledger-sonnet 포화, orbit-sonnet 55/60 동일
실패). 단 정직하게: 변동은 연속 분포가 아니라 **"`s`를 쓸까 말까" 단일
갈림길의 이분 분기**(AUROC이 두 값에만 몰림), 그리고 n=3의 2/3은 신뢰구간
약 0.2~0.94로 **"40~80% 밴드 진입"의 근거가 아니다**. 확인된 것은 양쪽
결과가 모두 발생한다는 존재 증명뿐 → p 추정은 본 수집 n=30에서.

**본 수집 전 정리 필요 2건:**
1. **함정을 프롬프트가 미리 알려준다 (구성 타당도).** `prompt.txt`의 CV
   경고 문장 + 저장소 이름 `ml-shift`. 세션 3이 자기 요약에서 "the project
   name and the hint about CV scores not reflecting held-out performance
   both signal distribution shift"라고 **두 힌트를 근거로 명시** → 성공 2건
   중 최소 1건은 데이터 진단이 아니라 힌트 판독. `docs/ML_ARM_DESIGN.md`에
   이 힌트에 대한 판단 기록이 없음(결정된 적 없이 들어간 문구).
   → 위 프로브로 해소.
2. **허위완료 지표가 이 과제에선 구조적으로 음성.** 3세션 전부
   `verified_end=1`·`unverified_completion_claim=false`. 실패한 세션 1도
   자체검증(aux 체크 7회) 후 "test passes, CV 0.979"로 보고 — **자기가 보는
   지표가 정반대를 가리키는** 설계이므로 "검증 없이 주장했나"는 다 음성이
   된다. 판별력을 가지려면 과제-특이 지표 = **"train과 test의 피처 분포를
   실제로 비교했는가"**를 트랜스크립트에서 추출해야 함(사후 산출 가능 →
   수집을 막지 않음). 조기신호 참고: 편집 전 탐색 6(실패) vs 4·7(성공),
   편집 전 커버리지 0.5/0.5/0.75 → n=3에선 무신호.

배치 첫 실행 시 러너가 `out_dir/.taskvenv` 1회 생성·설치(~1-2분) 후 세션
PATH 주입.

**러너 venv 배선 (`pilot/run_sessions.py`):** `ensure_task_venv`(template/
requirements.txt 있으면 out_dir/.taskvenv 1회 생성·설치, 배치 내 재사용),
`_session_env`(세션 PATH에 venv bin 주입). stdlib 과제는 None(무변경).
grade.py는 fallback 재실행 시 `.taskvenv` python 탐지. `tests/test_runner.py`
+4(무-requirements→None, PATH 주입, os별 bin, ml-shift requirements 존재).

**`ml-shift` 과제 (`pilot/tasks/ml-shift/`):** 분포 시프트+스퓨리어스 피처
`s`(train서 라벨 누출·test서 노이즈). 순진(전체 피처): train-CV 0.97·
held-out 0.60~0.65(실패); 세심(s 제거): CV 0.76·held-out 0.77~0.80(통과).
**보이는 지표(CV)가 정반대를 가리킴** = 허위완료 정통. τ=0.73. 결정론
데이터 생성기(`make_data.py`)+CSV 커밋, **채점기 stdlib**(AUROC Mann-Whitney,
sklearn은 세션 코드에만). `tests/test_ml_shift_task.py`(importorskip sklearn
→ CI 스킵, 코어 stdlib 청결). 로컬 검증: 레퍼런스 통과·naive visible통과/
held-out실패·템플릿 미구현. 상세 `pilot/tasks/ml-shift/README.md`,
`docs/ML_ARM_DESIGN.md`.

**W13 완료 (본 수집+신호 검정, PR #37~44 머지).** 밴드 사냥 종료
(구조적으로 막힘 — F1). 실증 결과:
(F1) 조건별 achievement는 거의 결정론적(schedule-haiku 28/30 동일 품질,
~50% 튜닝 불가), (F2) 변동은 효율·허위완료에 삶, (F3) 검증 신호는 실재하나
약·비일관(풀링 AUROC 0.66), (F4) 세션 독립성 방어. **다음 세션 선택지:**
(a) **(A) ML arm 설계** — sonnet도 실패하는 진짜 "방법 미확립"(held-out
성능, 의존성·컴퓨트·시드 machinery 신설), (b) **집필 착수** — 정직판 척추
(F1~F3, 제약 결과 포함)로 워크숍/논문, (c) 검증 신호를 더 두껍게(ledger-
haiku 스케일 등). 유저 결정 대기.

**수집 완료물 (로컬 gitignore):** `results/main2/{orbit-sonnet(n60,5성공),
layered-ledger-haiku(n30,26성공), schedule-haiku(n30,1성공)}`, `results/cal/
{schedule(sonnet3/3), layered-ledger(sonnet3/3)}` 등. 재현 분석:
`pilot/analysis/{session_independence,signal_validation}.py` (+테스트).

**확정된 과제 3종** (`pilot/tasks/{orbit-propagator,layered-ledger,
schedule}`): orbit=다중스케일 수치(유일 sonnet 실패), ledger=아키텍처 계약
(포화, 대조), schedule=makespan 방법-미확립 시도(sonnet 포화·haiku 바닥 —
achievement가 계층 가름). 전부 결정론 숨은 오라클.

**분석 초점 (haiku n=30 완료 시):**
- **읽기 조기신호 사망 확인**: `coverage_before_first_edit`·핵심부분집합·
  조사 길이가 성공/실패를 가르는가(AUROC). 프로브 n=3에선 실패 haiku#2가
  성공들과 편집 전 읽기 동일(핵심 3/3), sonnet 성공#2는 domain만 읽고
  즉시 편집 → **읽기 기반 조기신호는 메커니즘상 실패 예상**(실패는 읽기가
  아니라 구현 역량). n으로 확정.
- **검증-적정성 신호(데이터가 지지)**: 완료 주장 전 나머지-유발 비자명
  입력으로 자체검증했는가. orbit+ledger 공통 강건 판별자 = "보이는 테스트
  너머 자체검증 여부" + 허위완료. 기존 casa 지표(n_test_runs·aux·
  verified_end·unverified_completion_claim) + 트랜스크립트 사후 정밀분석.

**haiku 프로브 소견 (n=3, `results/cal/layered-ledger-haiku`):** 2/3 성공
(#2 실패 = `test_large_prime_split` 나머지 보존 위반 — 1000003/7에 전원
142858 배분, 합 1000006≠1000003 = 진짜 아키텍처 실패, 기술적문제 아님).
→ **haiku는 포화 아님(arm 성립), sonnet 천장 대조 실측.** #2도 허위완료
(검증 후 주장). 단 편집 전 커버리지는 성공=실패=0.83 → H-arch 미지지(n=1).

**보정 소견 (2026-07-25, sonnet n=3, `results/cal/layered-ledger`):**
표면 0/3이었으나 **셋 다 동일 원인 = 숨은 테스트 7개 중 `test_validation_gate`
하나만 실패**(n<=0을 `ValueError`로 거부 — 검증은 했으나 `ValidationError`
하위타입을 요구한 오라클 **과엄격**; template에 n 전용 검증 함수 없어 부당).
**오라클 수정(n은 `ValueError` 허용) 후 저장 workdir 재채점 → 3/3 통과.**
즉 **나머지 보존·정수 규율·단일 반올림 등 아키텍처 핵심을 sonnet이 전부
올바로 처리 → 포화.** 결정적으로 **#2는 편집 전 커버리지 0.17**(모듈 거의
안 읽음)인데도 핵심 통과 → **H-arch(편집 전 조사가 성패 예측) 검정 불가:
예측할 실패가 없음.** 파일럿 결론 재확인("sonnet은 계약 읽고 알려진 기법
적용 과제를 실패 안 함") — 6모듈 레이어링만으로는 sonnet 실패 유도 불가.
자백: split docstring에 conservation 불변식을 노출(설계는 코드로만 발견하게
하랬음)했으나, 숨겨도 분할=자릿수보존은 sonnet이 알아 결과 불변 예상.

**구현물 (`pilot/tasks/layered-ledger/`):** 계층형 원장(money→validation→
domain→serialize→repository→api) + 미구현 `domain.split_with_fee`. 숨은
오라클(나머지 보존·단일 반올림·정수 규율·검증 게이트, 전부 결정론 정수
비교), 레퍼런스 해답, naive 대조(보이는-통과·숨은-실패 실증). 신규 지표
`casa.metrics.coverage_before_first_edit`(H-arch 조기 신호) + compute_all
배선. 테스트: `tests/test_layered_ledger_task.py`(레퍼런스 통과·naive 분리·
템플릿 미구현), `tests/test_trajectory.py`(지표). 로컬 검증 완료(레퍼런스
success·오탐0, naive visible통과·hidden실패·float division 플래그).

**왜 전환했나 (orbit baseline 소견 → 구성 타당도):** orbit sonnet n=60
완주 결과 — 성공 5/60(8.3%), 실패 55건 **전부 보이는-통과·숨은-실패**(전부
위치오차 e=0.9), **허위완료 96%(53/55)이고 그 전부가 검증 후 주장**(정합축
강신호). 그러나 **궤적 분석: 조기판별 실패** — 자체검증 aux-check가 성패를
가르지만 100% 첫 편집 이후·중후반이라 AUROC@k는 k≤8에서 무신호(0.50),
k=16에서야 0.86. 원인 = orbit이 **단일 파일 수치 퍼즐**이라 CASA 간판 신호
(교차모듈 커버리지)가 죽고 판별이 후반 자체검증 하나로 쪼그라듦. 유저 실경험
(아키텍처 복잡성에서 실패)과 구성 불일치. → **달성·조기판별 축을 아키텍처
과제로 이관**(결정 로그 2026-07-25). orbit sonnet 60은 **정합축 데이터 +
"자체완결 수치과제는 조기판별 약함" 대조**로 보존(results/main2/orbit-sonnet).

**보류된 수집 배치 계획 (2026-07-24 "풀 ~230" — 축 전환으로 재검토 대상):**

| 과제 | 모델 | n | out | 상태 |
|---|---|---|---|---|
| orbit-propagator | sonnet | 60 | `results/main2/orbit-sonnet` | **완료(보존, 정합·대조)** |
| orbit-propagator | haiku | 60 | `results/main2/orbit-haiku` | 보류 |
| plugin-add | sonnet | 30 | `results/main2/plugin-add` | 보류(효율축, 피벗과 무관 — 재개 가능) |
| buggy-pipeline/config-parser/fee-calc/stable-roots | sonnet | 각20 | `results/main2/<task>` | 보류(효율축) |
| **아키텍처 과제(신설)** | sonnet | 보정 후 산정 | `results/main2/<new>` | **설계 중(ARCH_TASK_DESIGN.md)** |

커맨드 형식(재개 겸용): `.venv\Scripts\python.exe pilot/run_sessions.py
pilot/tasks/<task> -n <N> --model <sonnet|haiku> --out results/main2/<out>`.
러너 429 중단·재개(완료 세션 스킵) 보유. 효율 배치는 피벗과 독립이라
언제든 재개 가능(유저는 "설계 먼저"로 지금은 정지).

**W9~W12 완료·머지(PR #23~37).** W13은 규모 확정→orbit sonnet 60 수집
→baseline 분석→축 전환 결정까지 진행됨.

**지금까지 확립된 것 (요약; 상세는 docs/MAIN_EXPERIMENT.md):**
- 결과변수 3축 = 실제 달성 / 능력·효율(토큰·턴; wall-clock 금지) /
  주장-증거 정합(허위 완료·검증행동·하드코딩). casa 코어 지표로 구현됨
  (`casa.metrics`: verification_signals, claims_completion,
  unverified_completion_claim, tool_census).
- **과제 지형 (sonnet·haiku 4.5 각 보정 완료):**
  - orbit(다중 스케일) = **유일하게 실패하는 과제.** sonnet 27%,
    haiku 1/3; 두 계층 실패 모두 허위 완료 재현. → 달성·정합·허위완료
    축 담당.
  - config-parser·fee-calc·stable-roots·A·B = 두 계층 다 포화(3/3),
    토큰 ×1.7~1.8 분산. → **효율 축 전용.**
  - "약모델이면 실패" 전제 거짓: haiku 4.5도 완전명세 자체완결 과제는
    통과. 분리는 오직 다중 스케일에서.

**다음 세션 할 일 (W13):**
1. 본 수집 규모 확정(유저와): orbit sonnet n=40~60 + haiku n=40~60
   (달성·정합·허위완료), 효율 5과제 각 ~20~30. power.py로 재산정.
2. 실행: `pilot/run_sessions.py <task_dir> -n <N> --model <sonnet|haiku>
   --out results/main2/<task>-<model>`. **사용 한도(Max 5시간 창) 제약**
   — 배치 분할, 러너가 429서 중단·재개(완료 세션 자동 스킵). 시작 전
   `claude auth status` 확인.
3. 집계: `casa report results/main2/* --tasks-root pilot/tasks`.
4. NDroneFC arm 과제 정의(통제 반복 실행 — 실제 레포 외적 타당도).

**미해결(추적, 유저 요구):** sonnet 실패 달성 과제 추후 제작 = **다중
스케일 절벽형**(orbit 외 — 강성 반응계/경계층 PDE/특이적분; §8 후보).
일반 노력형 ODE는 sonnet·haiku 다 통과하므로 불가(진자 실측). 채택 전
"순진 균일 이산화 실패 / 세심 적응 통과" 실측 필수.

**보정 산출물 (로컬, gitignore):** `results/cal/{config-parser,fee-calc,
stable-roots,fee-calc-haiku,stable-roots-haiku,orbit-haiku}/` — 각 n=3.
본 수집은 `results/main2/`에 분리 저장 예정.

## 작업 분해 (파일럿까지)

| ID | 작업 | 상태 | 산출물 |
|---|---|---|---|
| W1 | buggy-pipeline 템플릿 + 채점기 | **완료** (2026-07-22, PR #2) | `pilot/tasks/buggy-pipeline/` |
| W1.5 | **수직 슬라이스**: 러너 프로토타입으로 W1 과제 세션 2~3개를 끝까지 (실행→트랜스크립트 수집→casa audit→채점) | **완료** (2026-07-23, PR #3·#4, G1 통과) | 러너 초안 + **게이트 G1 기록** |
| W2 | plugin-add 템플릿 + 채점기 (+ search-before-write 규칙 구체화) | **완료** (2026-07-23, PR #5) | `pilot/tasks/plugin-add/` |
| W3 | rename-sweep 템플릿 + 채점기 | **완료** (2026-07-23, PR #6) | `pilot/tasks/rename-sweep/` |
| W4 | 세션 러너 완성 (반복 실행, 버전 기록, 트랜스크립트 수집) | **완료** (2026-07-23, PR #7) | `pilot/run_sessions.py` |
| W5 | 궤적 지표 확장 (스텝별 누적 시계열, 궤적 유사도) | **완료** (2026-07-23, PR #8) | `src/casa/metrics.py` 확장 |
| W6 | 집계·분석 (`casa report`: 분산 통계, AUROC@k + Brier/ECE, 베이스라인 비교) | **완료** (2026-07-23, PR #18; diff 통계는 W9에서 워크디렉토리 기반 산출) | `src/casa/report.py` |
| W7 | 난이도 보정 (과제당 2~3세션, 40~80% 확인) → **게이트 G2** | **완료** (2026-07-23, G2 통과 — 게이트 기록 참조) | 보정 기록 → 이 파일 |
| W7.5 | 과제 D orbit-propagator (숨은 오라클 설계, 유저 제안) | **완료** (2026-07-23, PR #14, 보정 1/3) | `pilot/tasks/orbit-propagator/` |
| W8 | 파일럿 본 수집 (과제 4 × 15세션, sonnet) | **완료** (2026-07-24, 60/60, 오염 0) — A 15/15, B 15/15, C 13/15, D 4/15 | `results/main/` (gitignore, 로컬) |
| W9 | 분석 + go/no-go = **게이트 G3** (PILOT_DESIGN 사전 등록 기준) | **완료** (2026-07-24; §7~10 재검토·교정 포함, 3축 재설계로 귀결) | `docs/PILOT_RESULTS.md` |
| W10 | 3축 재설계 반영 (계획서 개정, 주장-정합 지표 코어 승격, 저장 audit 재생성) | **완료** (2026-07-24, 유저 승인) | RESEARCH_PLAN·PILOT_DESIGN 개정, `casa.metrics` 확장, `pilot/analysis/reaudit.py` |
| W11 | 본 실험 설계 구체화 (과제 세트 개편: 숨은 오라클형 중심 + 효율 측정용, 규모 산정) | **완료** (2026-07-24, 설계서+규모 산정 — 유저 승인 대기) | `docs/MAIN_EXPERIMENT.md`, `pilot/analysis/power.py` |
| W12 | D2·E·F 과제 구현 + census 배선 + 양계층 보정 | **완료** (2026-07-24, PR #28~35). D2 config-parser·E fee-calc·F stable-roots 구현; census(`tool_census`); sonnet·haiku 4.5 보정 → 트랩 3종 두 계층 포화, orbit만 실패(허위완료 재현). 지형 확정 → MAIN_EXPERIMENT §8 | `pilot/tasks/{config-parser,fee-calc,stable-roots}/`, `casa.metrics` |
| W13 | 본 수집 + 3축 분석 → **축 전환**(아키텍처 복잡성 과제) | **진행 중** (orbit sonnet 60 완료·분석 → 조기판별 실패로 아키텍처 과제 설계로 피벗, 수집 보류) | `results/main2/`, `docs/ARCH_TASK_DESIGN.md` |
| W14a | ML arm `ml-shift` (설계·과제·러너 격리 venv·sonnet 보정) | **진행 중** (2026-08-19: 보정 2/3 기록 완료 → 힌트 제거판 n=3 프로브 대기) | `pilot/tasks/ml-shift/`, `docs/ML_ARM_DESIGN.md`, `results/cal/ml-shift` |
| W-later | sonnet 실패 달성 과제(다중 스케일 절벽형, orbit 외) | 추적 (유저 요구) | `pilot/tasks/<new>/` |
| W13 | 본 수집 ~180세션 (배치 분할, 원자료 보존) | 대기 | `results/main2/` |
| W14 | 3축 분석 → 사전 등록 판정 → 집필/학회 결정 | 대기 | 분석 노트 |

상태 값: 대기 / 진행 중 / 완료 / 보류(사유 명기). 의존성: **W1 → W1.5(G1)
→ 나머지**. G1 통과 후 W2~W3 병렬 가능, W7은 W2~W5 필요, W8은 W7(G2) 필요.

## 방향 점검 게이트 (마일스톤 기반 — 시간 기반 아님)

각 게이트는 "다음 단계의 비용을 쓰기 전 마지막 지점"에 있다:

- **G1** (W1.5 직후, 템플릿 2개 더 만들기 전): 헤드리스 반복 실행·수집·감사·
  채점 파이프라인이 실제로 도는가? 안 돌면 여기서 멈추고 방법을 다시 찾는다.
- **G2** (W7 직후, 45~60세션 본 수집 전): 성공률이 40~80% 구간인가? 보정
  세션들의 행동 지표가 실제로 흩어지는가? 분산이 바닥이면 본 수집은 낭비다.
- **G3** (W9, 본 실험 전): PILOT_DESIGN 사전 등록 기준으로 go/no-go.

**모든 게이트에서 같은 질문 5개를 묻고 결과를 이 파일에 기록한다:**

1. 지난 게이트 이후 산출물이 논문의 척추(실증 발견)에 기여했는가, 도구
   장식이었는가? ("도구는 주인공이 아니다" — RESEARCH_PLAN)
2. 사전 등록 기준을 여전히 통과할 수 있어 보이는가? 아니라면 기준 수정
   vs 설계 수정 중 무엇인지 결정하고 결정 로그에 남긴다 (사후 조작 방지)
3. 노벨티 워치 (10분 arXiv 표적 검색): 2605.28840 / 2603.29231의 개정·후속
   + 신규 동시 연구. 발견 시 RELATED_WORK.md 갱신
4. 설계 원칙(CLAUDE.md) 위반 없는가 — 결정론적 코어, 프롬프트 강제 금지 등
5. **게이트 요약을 유저에게 보고하고 계속/조정 결정을 받는다**

### 게이트 기록

**G3 — 2026-07-24 — 판정 완료, go/no-go 유저 결정 대기**

분석 전문은 `docs/PILOT_RESULTS.md`. 사전 등록 기준: RQ1 미충족(성공률
창 40~80%에 든 과제 0 — A·B 100%, C 87%, D 27%), RQ2 미충족(pooled
AUROC@first-edit 최대 0.62; 유일한 실질 실패 표본인 D에서 탐색 신호가
역방향 0.33 — 숨은 오라클형은 수정 후 검증 루프가 성패 결정), H1b
미지지(금지형 6 vs 의무형 4, 의무형은 단일 세션), RQ3 "60% 첫 2스텝"
재현 안 됨(분리는 k=12~20에서야), 준수×일관성만 방향 긍정(위반 5세션
전부 과제 평균보다 느림, 실패율 40% vs 20%). 계획 밖 발견 F2 = **배치
수준 국면 전환**: C 보정 84~160초·33% → 본 배치 435~929초·87%, D 429
전 1/7 → 후 3/8, 전 세션 모델 ID 동일(claude-sonnet-4-6) — 기록된
버전으로 설명 불가, 시간대·부하와 교란. G2의 "sonnet 준수 천장"은
n=60에서 수정(위반 5세션/8.3%). 5문항: (1) 실증 기여 ✓ — F2·천장 수정·
RQ2의 과제 유형 의존성 모두 논문 척추감 (2) 사전 등록 기준 — 문구상
"모두 약하면 보류" 경로에 해당, 기준 완화 없이 판정 기록(사후 조작
없음); 재설계 방향은 유저 결정으로 (3) 노벨티 워치 — 2605.28840 개정
없음·2603.29231 후속 없음; 신규 2편 검증 후 반영(2605.10039가 CLAUDE.md
준수 실증 선점 → 빈자리 3 축소, 2605.29442 실사용 오정렬 분류) →
RELATED_WORK 갱신 (4) 설계 원칙 ✓ — 분석 전부 결정론(stdlib), 프롬프트
강제 없음, 픽스처 무수정 (5) 유저 보고 — 2026-07-24 보고, 결정 대기
(선택지는 "다음 세션 시작점" 참조).

**G2 — 2026-07-23 — 부분 통과, 난이도 조정안 유저 결정 대기**

보정 (sonnet 4.6, 과제당 3세션, ~$0.3/세션): A 3/3·B 3/3 성공(너무 쉬움,
40~80% 상단 초과 — 특히 B는 테스트 docstring의 형식 예시가 관례 조사를
불필요하게 만든 설계 결함, coverage 0.2·탐색 0~2), C 1/3(실패 2건은
pytest 통과 후 docstring 잔존 리터럴 — 설계 의도대로 철저함이 성패를
가름; 성공 세션 coverage 1.0 vs 실패 0.7/0.9 = **RQ2 신호 초기 확인**).
위반 12세션 연속 0 — sonnet은 이 규칙 세트를 사실상 완벽 준수, 준수
분산·H1b 데이터 부족 리스크; 과제가 2~3분으로 짧아 길이 의존 가설
(H1b)에 구조적으로 불리한 점도 인지. 제안: B(docstring 예시 제거+계약
미묘화)·A(버그 미묘화) 조정 후 재보정, C 유지. → 유저 승인(①), 2026-07-23 조정 적용
(PR #11): A 힌트 제거(명세는 models.py에만, 테스트·픽스처 이름 중립화),
B docstring 예시 제거 + 채점기 숨은 관례 검사 3종(export 오버라이드/모듈
위치/여분 필드). A·B 재보정 진행.

**G2 최종 — 2026-07-23 — 통과 (본 수집 진입 승인 대기)**

최종 매트릭스 (sonnet 4.6, 과제당 3세션): A 3/3(포화 — 행동 분산 담당,
탐색 2~10·coverage 0.4~0.8), **B 2/3**(3차 조정 후 구간 진입 — "편집
파일의 지시를 읽는가"가 판별), **C 1/3**(문서 스위프), **D 1/3**(숨은
오라클 — 실패 2건 모두 visible 통과+hidden 실패로, 포화 차단이 실세션
에서 관측됨. 세션당 3~11분, $0.3~0.8). 결과 분산 과제 3종(B/C/D) 확보,
C·D는 하단 경계(33%)이나 n=3 신뢰구간이 넓어 조정 없이 본 수집 진입,
필요시 D 손잡이(허용오차 배율)로 사후 조정. 위반: sonnet 21세션 누적 0
(haiku에서만 1건) — "sonnet의 규칙 준수 천장"을 파일럿 발견으로 보고
예정, H1b는 세션 길이 한계와 함께 한계 절로. 5문항: 실증 기여 ✓(과제
설계 자체가 "테스트 완전 명세 과제는 포화된다"는 방법론적 발견 생산) /
사전 등록 기준: 성공률 구간은 B만 엄격 충족, C·D 경계 — 기준 완화 없이
n 증가로 판정 (사후 조작 방지, 결정 로그 기록) / 노벨티 워치: 07-23
검증 8편 반영 완료, 신규 위협 없음 / 설계 원칙 ✓ (숨은 오라클도 결정론
채점) / 유저 보고: W8 승인 요청 중.

**G1 — 2026-07-23 — 통과 (조건부 주의 2건)**

수직 슬라이스: buggy-pipeline × 3세션 (sonnet 4.6, 헤드리스
`--dangerously-skip-permissions`, 프롬프트는 stdin 전달). 3/3 성공,
세션당 ~2분·~$0.3. 전 세션 트랜스크립트 수집·파싱 무손실(skipped_lines=0
— 파서가 현행 포맷과 정합), coverage 1.0/0.8/0.8, 탐색 11/10/9,
카나리아 위반 0 (전 세션이 커밋 수행 → git 규칙 실제 트리거·준수 확인).

5문항: (1) 실증 기여 — 파이프라인 생존성 확립 + 파서 실데이터 검증, 도구
장식 아님. (2) 사전 등록 기준 전망 — **주의 A**: 3/3 성공은 sonnet 기준
성공률이 40~80% 상단을 벗어날 신호; n=3이라 미확정, W7 보정에서 난이도
상향(결함 미묘화) 대비. **주의 B**: 위반 0 — 준수가 진짜로 높다면 위반
데이터 부족 위험; W7에서 위반율도 보정 관찰 대상에 포함할 것. (3) 노벨티
워치 — 전일(07-22) 딥서베이 수행, 변화 없음. (4) 설계 원칙 — 결정론 코어
유지, 프롬프트 무규칙 유지, 위반 없음. (5) 유저 보고 — 2026-07-23 보고,
계속 결정 대기.

운영 교훈(W4 반영): OAuth 토큰 만료가 실행 전 발생 가능 — 러너는 시작 전
`claude auth status` 확인 + 만료 시 즉시 중단 필요. Windows에서 프롬프트는
반드시 stdin으로(명령줄 전달 시 cmd.exe가 여러 줄 인자를 파괴).

## 결정 로그 (뒤집으려면 유저와 상의)

- 2026-08-19 **ml-shift sonnet 보정 결과 기록 + "힌트 제거판 프로브를 본
  수집 앞에 둔다"** (유저 승인). 보정 2/3(held-out AUROC 0.6423 실패 /
  0.7973 / 0.7973, τ=0.73) — **같은 조건에서 성공·실패가 둘 다 나온 첫
  과제**로 F1(조건별 achievement 결정론성)의 첫 반례. 단 밴드 진입 주장은
  하지 않는다(n=3의 2/3은 CI 약 0.2~0.94; 변동은 "`s` 사용 여부" 단일
  갈림길의 이분 분기). **미결 리스크 = 프롬프트가 함정을 예고**: prompt.txt
  의 CV 경고 문장 + 저장소명 `ml-shift`를 세션 3이 성공 근거로 명시 인용.
  → 본 수집(n=30, ≈$16) 전에 중립 이름·힌트 삭제판 n=3(≈$1.6)을 돌려
  조건을 확정한다. 힌트 유지·삭제 중 어느 쪽이든 이 기록으로 방어(사후
  선택 금지). 부수 확인: `unverified_completion_claim`은 이 과제에서 구조적
  으로 전건 음성(실패 세션도 자체검증 후 주장) → 판별은 "train/test 분포를
  비교했는가" 과제-특이 지표로, 트랜스크립트 사후 산출.
- 2026-07-25 **밴드 사냥 종료 + "조건별 achievement 결정론성"을 발견으로
  수용** (유저). 근거: schedule-haiku 30세션 총 최적성 갭 [0,2,8×28] =
  28/30 동일 품질, 손잡이로 ~50% 도달 불가(OPT+1 7% → OPT+2 100% 절벽).
  → 조기 성공 예측의 대상 분산이 조건 내엔 거의 없음. 실효 신호는 효율·
  허위완료(F2), 단 검증 지표는 약·비일관(F3, 풀링 AUROC 0.66). 기존 혼합
  조건(orbit-sonnet·ledger-haiku)으로 검정 완료, 새 밴드 수집 안 함.
  전문 `docs/W13_FINDINGS.md`. 성공률 튜닝 지양 지침([[dont-fixate-on-
  success-rate]])과 정합.
- 2026-07-25 **난이도 기준 = "목표 명확·방법론 미확립"** (유저 제안·채택).
  근거: 포화 과제(trap 3종·ledger)의 공통점은 방법이 확립됨(검색-후-적용)
  → 강모델 실패 안 함. orbit만 실패한 건 방법 미확립(다중 스케일 → 적응
  스텝 고안·검증). 유저 일반화: 목표는 객관적이나 방법이 레시피가 아닌
  과제라야 역량·노력 변동+허위완료가 생김. 실현: **(B) stdlib 휴리스틱
  먼저**(결정론·의존성0로 기준 검증) → 되면 **(A) ML 모델 개발**로 격상
  (유저 실경험 근접, 시드·컴퓨트·의존성 machinery 신설). 첫 과제=`schedule`
  (makespan, held-out 적대 인스턴스, 목표=OPT). layered-ledger는 대체(달성·
  조기판별 spine에서 내림), orbit·ledger는 대조로 보존.
- 2026-07-25 **세션 간 독립성 검정 = 방법론 방어로 확립** (유저: 논문
  threats-to-validity 핵심). "반복 실행 시 세션 간 상태 공유로 결과가
  수렴하면 세션 간 변동성이 인공물"이라는 위협을 구조(격리)+행동(수렴
  없음)으로 반증. 구조: 세션마다 template 새 복사·별개 git·별개 트랜스크립트
  project dir(work-NN), 유저 레벨 공유 메모리/CLAUDE.md 부재, 프롬프트
  캐시는 해답 미전달·온라인 학습 없음. 행동(재현 스크립트 `pilot/analysis/
  session_independence.py` + `tests/test_session_independence.py`): orbit
  sonnet n=60 → 성공률 전/중/후 5%/15%/5%(수렴 추세 없음), 궤적 유사도
  인접 0.386 vs 먼 쌍 0.371(Δ=+0.015). → RESEARCH_PLAN 리스크표에 반영.
- 2026-07-25 **달성·조기판별 축을 아키텍처 복잡성 과제로 전환** (유저).
  근거: orbit sonnet n=60 baseline 궤적 분석이 조기판별 실패(자체검증이
  후반 신호, AUROC@k≤8 무신호)를 보였고, 이는 orbit이 단일 파일 수치
  퍼즐이라 CASA 간판 신호(교차모듈 커버리지)가 죽은 인공물. 유저 실경험은
  아키텍처 복잡성에서 실패 → 구성 타당도 불일치. **목적제작 아키텍처 과제
  신설**(계층형 원장+교차 불변식 숨은 오라클; `docs/ARCH_TASK_DESIGN.md`),
  orbit은 정합축·대조로 강등·보존. **수집 전면 보류(설계 먼저).** 효율
  배치는 피벗과 독립이나 유저 지시로 함께 정지. NDroneFC arm(로그된 외적
  타당도 vehicle)은 이 아키텍처 방향의 실제-레포 짝으로 유지. 뒤집기 전
  ARCH_TASK_DESIGN 승인 절차 참조.
- 2026-07-24 **W13 본 수집 규모 확정 = "풀 ~230"** (유저 선택). 배분:
  orbit sonnet 60 + orbit haiku 60(척추 — 달성·정합·허위완료) + 효율
  5과제(plugin-add 30, buggy-pipeline·config-parser·fee-calc·stable-roots
  각 20 = 110). 총 230세션. 시작 배치 = orbit sonnet(유저 지정). NDroneFC
  arm은 과제 정의 선행이라 이번 7배치 밖(W13 후반 추적). 근거·재개 절차는
  "본 수집 배치 계획" 표 참조. W12 지형 확정(orbit만 3축, trap 3종은 효율
  전용)으로 구 180안(D/D2/E×40) 폐기, 양계층 orbit 중심으로 재배분.
- 2026-07-24 **달성·허위완료 축 = orbit 증량 + 약모델(haiku) arm 병행**
  (유저). 근거: 트랩 과제 3종(parser/fee/roots) 전부 sonnet 3/3 포화 +
  진자 실측으로 "일반 orbit류 노력 과제는 sonnet 실패 불가"(다중 스케일
  절벽만 실패, MAIN_EXPERIMENT §8) 확인. → sonnet 달성 데이터는 orbit
  단독(n 증량), 실패·허위완료 스펙트럼은 haiku arm에서 확보하고 sonnet↔
  haiku 대조("완전명세 천장")를 발견으로 보고. **미해결(추적): sonnet을
  실패시키는 달성 과제를 추후 별도 제작**(다중 스케일 절벽형 — orbit 외
  두 번째 도메인; 설계 난도 높음, 유저 명시 요구).
- 2026-07-24 **본 실험 4개 결정 확정** (유저): ① 실제 레포 arm =
  **NDroneFC를 통제 반복 실행**(순수 관찰 아님 — 프로젝트가 안정적이라
  새 세션 표본이 부족하므로 우리 정의 과제를 그 레포 위에서 반복; 외적
  타당도 방어). ② **D2 도메인 = 파서 상태기계**(결정론 채점 확실; 동시성
  카운터는 경쟁 조건 타이밍 의존으로 채점 재현성 위협이라 기각). ③ 규모
  = **sonnet 전체 계획 180세션 승인**(제약은 달러가 아니라 Max 정액제의
  5시간 사용 한도 — 배치 분할로 흡수, 러너 429 재개 보유). ④ 축소안
  (D2 생략) 불채택.
- 2026-07-24 **3축 재설계 승인** (유저): 결과변수 = 실제 달성 / 능력·
  효율(토큰·턴) / 주장-증거 정합. 본 실험 판정 기준을 PILOT_DESIGN
  "파일럿 이후 개정" 절에 사전 등록(효율 스프레드 재확인, 허위 완료율
  ≥50% 재현, 검증-신호 AUROC ≥ 0.7 등). 주장-정합 지표는 casa 코어로
  승격, 저장 audit는 셸 인지 파서로 재생성(reaudit 스탬프).
- 2026-07-24 **셸 사각지대 수정** (파서·규칙): Claude Code의 PowerShell
  도구를 Bash와 함께 셸로 취급(`SHELL_TOOLS`), 규칙 YAML `tool: Bash →
  Shell`(자연어 규칙이 셸 중립이므로 의미 원복). 60세션 중 44세션이
  PowerShell 사용 — 구 파서는 이들의 탐색·검증·git 활동을 못 봤고,
  이 때문에 §7 "검증 지표 무신호"가 오판(교정 후 D 수정→테스트 사이클
  AUROC 1.0), D#11 의무형 위반 4건이 인공물이었음. PILOT_RESULTS §9.
  후속: results/main 세션 JSON의 저장 audit 재생성 스크립트(본 실험 전).
- 2026-07-24 **결과변수에 "주장-실제 간극" 축 추가** (유저 현상 지목):
  실패 13세션 중 12건이 완료 단언(허위 완료 92%), 1건은 무보고 중도
  정지 — 자기 보고는 신호 가치 0, "주장 이전 검증 실행 존재"가 강신호.
  PILOT_RESULTS §10. 재설계는 성공/능력(토큰·턴)/주장 정합의 3축으로.
- 2026-07-24 **wall-clock 시간(및 파생 지표)을 행동·능력 지표에서 제외**
  (유저 지시): 접속 수·대역폭 등 서빙측 교란이 지배적. 이에 따라 배치
  국면 전환(PILOT_RESULTS §3)은 시간 배제 재검정에서 유의성 상실(C Fisher
  p=0.108, D p=0.569) → "시사적 관찰"로 강등. 능력·효율은 턴/토큰/비용
  같은 내용 기반 지표로만 측정.
- 2026-07-24 **연구 관심 정교화** (유저 명시): 성공/실패 이분법이 아니라
  "같은 프로젝트에서 새 세션마다 달라지는 **업무 처리 능력**을 조기
  판별해 시간·토큰 절약"이 목표. 기존 행동 지표(탐색 수·커버리지·검증
  횟수)는 타당성 재검토 대상(파일럿에서 무신호/역신호 실증 —
  PILOT_RESULTS §7). 유저가 제안 방향(시간대 소배치 반복) 기각 —
  재설계 방향은 §8 함의 기반으로 유저 결정 대기.

- 2026-07-23 **본 수집 모델 = sonnet 확정** (유저 승인). 근거: 3차 보정
  매트릭스 — sonnet은 B 2/3(구간 내)·C 1/3(경계), haiku는 B 0/3·A/C
  포화로 가용 셀 없음. haiku 데이터는 모델 계층 교차 비교용으로 보존.
- 2026-07-23 **과제 D(orbit-propagator) 추가** (유저 제안·승인): 난이도
  상향은 "난제 출제"가 아니라 **숨은 오라클**(수학·물리 정답이 정의하는
  채점 전용 계약 스위트)로 — 포화를 구조적으로 차단하면서 객관 채점
  유지. 허용오차는 실측으로 설정(Euler·leapfrog·교과서 RK4 실패, 서브
  스텝 RK4 정답 여유 ≥10배). B 3차 조정(필수 편집 파일에 포인터)도
  같은 날 확정 — "편집하는 파일의 지시를 읽는가"가 판별축.

- 2026-07-22 연구 초점 = **세션 간 변동성** (compaction/H1a 폐기, 공변량으로만
  기록). 유저가 명시 지시. → docs/RESEARCH_PLAN.md
- 2026-07-22 선행 연구 딥서베이 완료. 노벨티 스코핑: 실 코딩 에이전트 +
  within-run 조기 예측 + 블랙박스 + 준수×일관성 공분산. 최근접 경쟁:
  arXiv 2605.28840, 2603.29231. → docs/RELATED_WORK.md
- 2026-07-22 파일럿 과제 3종 확정 (buggy-pipeline / plugin-add /
  rename-sweep). → docs/PILOT_TASKS.md
- 2026-07-22 Python 환경 = 프로젝트 `.venv/` 필수. 훅도 venv python 명시
  호출 (Windows: `.venv\Scripts\python.exe`).
- 2026-07-22 GitHub private 저장소 https://github.com/elecage/casa 로 동기화.
- 2026-07-22 개발 규칙 강화: 모든 코드 변경은 테스트 동반, main 직접 push
  금지 — 피처 브랜치 + PR + CI(GitHub Actions, Ubuntu/Windows ×
  py3.10/3.13) 녹색이어야 머지. → CLAUDE.md Working rules
- 2026-07-22 하네스 완비: .gitattributes(줄바꿈 정규화), pre-commit 훅
  (scripts/git-hooks — pytest+main 커밋 차단, clone당 1회 core.hooksPath
  설정 필요), 프로젝트 .claude/settings.json(권한 허용 목록 + CASA 셀프
  감사 훅 배선 — hooks/run.sh 경유), PR 템플릿. 브랜치 보호는 무료 플랜
  private라 불가(관례+pre-commit으로 대체, public 전환 시 재시도).

- 2026-07-23 외부 문헌 정리안의 신규 후보 8편 병렬 검증 → 7편 확정·1편
  부분(2603.25764: 실제 제목 "Confident and Wrong", "71%" 수치는 날조 —
  실제 68~80%). RELATED_WORK에 반영: Bjarnason 60k 궤적(배경 핵심 인용),
  Confident and Wrong(일관성≠품질 해독제+쌍봉 긴장), 지시 준수·절차 절
  신설(AgentIF/PAE/InferAct/FixedBench), Baltes EMSE 가이드라인(보고
  준거), Zhou retry-free, Majgaonkar 72~81% 각도. 교훈: 외부 LLM 정리의
  인용은 반드시 검증 후 채택 (제목·수치 오류 실재).
- 2026-07-23 외부 리뷰(유저 제공 ChatGPT 정리안) 비교 후 5개 보강 채택:
  calibration 지표(Brier/ECE)·베이스라인 4종·재시작 오탐 비용·diff 라벨·
  세션 지속성 개념 프레임(+부차 arm 후보). 개입 정책 구현·학습 예측기·
  사람 평가·세션당 다과제 1차 설계는 기각. → RESEARCH_PLAN/PILOT_DESIGN
- 2026-07-23 저장소 **public 전환** (유저 결정) + main 브랜치 보호 활성화:
  CI 4개 체크 필수, 관리자 포함 강제, force-push/삭제 차단. 배경: 무료
  플랜 private에서 Actions 결제 실패로 CI 미실행 + 빨간 CI 머지 사고
  1회(PR #4, 로컬 테스트는 통과 상태였음) — 이제 서버가 차단.

## 미해결 / 주의

- ~~W9 분석 1순위 단서~~ → W9에서 분석 완료 (PILOT_RESULTS §3 F2):
  model_versions는 60세션 전부 동일(claude-sonnet-4-6) — 기록된 버전으로
  설명 불가, 배치 수준 국면 전환으로 정리. D 429 전후 비교도 같은 방향.
  교훈: 보정 배치 원자료를 보존 안 해 C 비교가 대화 기록 의존 — **이후
  모든 배치 원자료 보존**.
- 본 실험 진입 시 도구 처리 2건: diff 통계의 `__pycache__`/바이너리
  필터, "불필요 수정" 라벨용 과제별 편집 허용 목록(relevant_files는
  읽기-커버리지 목록이라 겸용 불가) — PILOT_RESULTS §6.
- results/ 전체 938MB (워크디렉토리 git 포함). 타 머신 분석 시 경량
  복사(session/transcript/summary/meta JSON만, ~수십 MB)로 casa report
  전체 동작 — diff 통계만 워크디렉토리 필요.

- W4 러너 완성 시 반영할 것 (G1 교훈): 시작 전 `claude auth status` 게이트,
  장기 수집 중 토큰 만료 시 중단·재개 처리, 프롬프트 stdin 전달 유지.
  슬라이스는 sonnet으로 실행 — 본 수집(W8) 대상 모델은 G2 전에 결정.
- ~~canary-search-before-write 플레이스홀더~~ → W2에서 해결: 과제 로컬
  canary_rules.yaml 오버라이드 방식 (러너 rules_for). 기본 파일의
  플레이스홀더는 유지 (Write가 드문 과제에서 오탐 방지).
- 투고 직전 재확인: 최근접 프리프린트 2편의 개정/심사 상태 + ICSE/FSE/ICLR
  워크숍 동시 연구 표적 검색 (RELATED_WORK "열린 확인 사항").
- **미해결(유저 요구, 추후):** sonnet을 실패시키는 달성 과제 제작. 실측
  결론(§8): 일반 노력형 ODE 불가, orbit식 **다중 스케일 절벽**(한 영역이
  다른 영역보다 훨씬 빠른 동역학 → 균일 이산화 과소해상)만 실패 유도.
  후보 도메인: 고이심률 궤도 외 — 강성 반응계(stiff chemistry), 경계층
  PDE, 특이적분(near-singular quadrature). 각 후보는 orbit처럼 "순진 균일
  이산화 실패 + 세심 적응 통과"를 실측 확인 후 채택.
