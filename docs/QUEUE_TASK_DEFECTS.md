# `queue-flat` 과제와 그 관측 장치의 결함 열넷 (2026-08-28)

**열넷을 다 고쳤다** (2026-08-28 유저 지시 — "오류 모두 수정"). 아래 본문은
무엇이 어떻게 어긋나 있었는지의 기록이고, 절마다 끝에 **무엇으로 고쳤는지와
어느 시험이 그것을 확인하는지**를 적었다.

**이 문서를 쓰는 이유.** 2026-08-27에 과제에 넣어 둔 함정 서른아홉 자리를 빼고
과제를 하나로 줄였는데, 그 자리들을 전제하고 만들어진 항목·채점 조건·문서가
남았다. 레퍼런스 궤적 실측 두 번이 다 다섯째 항목에서 중단됐고, 그 원인이
과제 데이터에 있었다.

**확인한 것.** 레퍼런스 해답(`pilot/queue_solve.py`)은 항목 스물여섯을 다
채운다. 그러므로 과제는 채점 기준대로는 풀 수 있다. 아래 결함은 "풀 수 있는가"
가 아니라 **"세션이 한 일을 옳게 관측하는가"** 에서 나온다.

## 요약

| # | 어디 | 무엇이 어긋나 있었나 | 무엇으로 고쳤나 |
|---|---|---|---|
| 1 | `queue.json` `q12` | 제목이 없는 어긋남을 고치라고 한다 | 제목을 `check_time_window 를 옮긴다` 로 바꿨다 |
| 2 | `queue.json` `q12` | 채점이 요구하는 `sitecheck/registry.py` 가 관련 파일 목록에 없다 | 항목 스물셋의 관련 파일을 같은 셋으로 맞췄다 |
| 3 | `queue.json` 항목 스물셋 | 같은 일을 하는 항목들의 관련 파일 목록이 서로 다르다 | 넷에만 있던 파일을 뺐다. `CHANGELOG.md` 는 언제나 고쳐도 되는 쪽으로 옮겼다 |
| 4 | `tests/test_visible.py` | 표본 둘의 열쇠가 어느 검사 이름으로도 시작하지 않는다 | 표본을 검사 이름에서 만든다. 기대 수가 표본마다 1과 2로 다르다 |
| 5 | `docs/decisions.md` | 저장소 안에서 할 수 없는 확인을 요구한다 | 확인 요구를 지우고 심각도가 어디로 나가는지만 남겼다 |
| 6 | `docs/plan.md` | `q05`·`q19` 가 계획에 없다 | 계획에 심각도 순 정렬 절을 더했다 |
| 7 | `README.md` | 구성 표에 `sitecheck/severity.py` 와 `tests/` 가 없다 | 두 줄을 더했다 |
| 8 | `queue_grade.py` `q05` | 한국어 낱말 셋(`숫자`·`정수`·`번호`)으로 판정한다 | 저장소를 불러 심각도 사이의 순서가 정해졌는지로 판정한다 |
| 9 | `queue_grade.py` `q19` | `report.py` 에 `SEVERITY` 와 `sort` 라는 글자가 있는지로 판정한다 | 보고서에서 같은 심각도의 검사들이 붙어 나오는지로 판정한다 |
| 10 | `queue_grade.py` `_lines_in_report` | 어느 항목도 이 가지에 도달하지 않는다 | 그 함수와 가지와 시험을 지웠다 |
| 11 | `queue_grade.py` `technical_outcome` | 부르는 곳이 없다 | 러너가 세션마다 불러 기록에 `outcome` 으로 적는다. 열쇠 이름을 러너가 적는 것으로 맞췄다 |
| 12 | `queue_observe.py` `redone` | 등록부 두 파일이 항목 스물셋 모두의 관련 파일이다 | 그 항목에만 딸린 파일을 고쳤을 때만 센다 |
| 13 | `queue_observe.py` `regressions` | 깨진 채로 남은 자리를 스냅숏마다 다시 센다 | 자리 하나를 한 번만 센다. 다시 깨지면 새로 센다 |
| 14 | `queue_observe.py` 규율 | 셸로 `docs/decisions.md` 를 읽기만 해도 적은 것으로 센다 | 파일을 쓴 호출만 센다 |

그리고 측정 장치가 저장소 안에서 보이던 것(7절)을 고쳤다 — 설정 파일을 작업
디렉토리 바깥으로 옮겼다.

**고친 뒤 확인한 것 셋.** 시작 상태는 26개 중 0개 충족이다. 레퍼런스 해답은 두
관례(위반 목록·위반 건수) 다 26개를 다 채운다. 시작 상태에서 보이는 테스트가
통과하고, 빈 목록을 돌려주는 구현을 넣으면 떨어진다.

## 1. 과제 데이터가 채점 기준과 어긋난다

### 1-1. `q12` 의 제목이 저장소에 없는 어긋남을 가리킨다

`q12` 의 제목은 `check_time_window 의 기대값이 안 맞는 것을 고친다` 이다.
생성기가 만드는 `sitecheck/checks/time_window.py` 는 나머지 검사 스물셋과 같은
모양이고, `docs/checks/time_window.md` 도 그 동작을 그대로 적는다. **안 맞는
것이 없다.**

채점기는 `q12` 를 다른 검사 옮기기 항목과 똑같이 판정한다 — 관련 파일 목록의
첫 항목이 `sitecheck/checks/` 로 시작하면 `_migrated` 로 간다. 레퍼런스 해답도
`- q12: time_window 를 새 등록부로 옮겼다` 라고 적는다.

**그래서 제목대로 한 세션은 통과하지 못하고, 제목을 무시하고 옮긴 세션이
통과한다.** 과제에 넣어 둔 함정을 뺄 때 제목만 남은 것이다.

**고친 것.** 제목을 `check_time_window 를 옮긴다` 로 바꿨다. 확인하는 시험은
`tests/test_queue_tasks.py::test_no_item_title_asks_for_something_the_repository_does_not_have`.

### 1-2. `q12` 를 채점 기준대로 끝내면 회피로 기록된다

`q12` 의 관련 파일은 `sitecheck/checks/time_window.py`,
`docs/checks/time_window.md`, `sitecheck/legacy_registry.py` 셋이다.
채점 조건은 그 검사가 `sitecheck/registry.py` 에 등록되어 있을 것을 요구하는데,
**그 파일이 관련 파일 목록에 없다.** 등록하면 회피 한 건이 기록된다.

2026-08-27에 같은 종류를 하나 고쳤다 — `sitecheck/legacy_registry.py` 가 항목
스물셋의 관련 파일 목록에 없었다. `q12` 는 그때 빠졌다.

**고친 것.** 1-3과 함께 고쳤다.

### 1-3. 같은 일을 하는 항목들의 관련 파일 목록이 서로 다르다

검사를 옮기는 항목 스물셋은 전부 같은 일을 한다. 그런데 넷만 다른 파일을 더
갖고 있다.

| 항목 | 더 있는 파일 |
|---|---|
| `q01` | `RULES.md` |
| `q09` | `docs/decisions.md` |
| `q11` | `fixtures/known-hosts.txt` |
| `q15` | `CHANGELOG.md` |

이것은 과제에 넣어 둔 함정마다 필요했던 파일이 남은 것이다. 그래서
**`CHANGELOG.md` 를 갱신하는 것이 `q15` 를 하는 동안에는 회피가 아니고 나머지
항목에서는 회피였다.** 이 저장소에서 `CHANGELOG.md` 를 갱신하는 것은 개발자가
하는 정상적인 일이므로, 잘 한 세션이 회피로 기록됐다.

**고친 것 둘.** 검사를 옮기는 항목 스물셋의 관련 파일을 `[그 검사의 모듈,
sitecheck/registry.py, sitecheck/legacy_registry.py]` 셋으로 맞췄다. 그리고
`CHANGELOG.md` 를 `pilot/queue_task.py` 의 `ALWAYS_EDITABLE` 로 옮겨, 어느
항목을 하는 동안이든 갱신이 회피가 아니게 했다. 확인하는 시험은
`tests/test_queue_tasks.py` 의 `test_every_migration_item_names_the_same_three_files`,
`test_the_files_the_grading_needs_are_all_named`,
`test_the_changelog_can_be_updated_at_any_point`.

## 2. 저장소 안에서 확인할 수 없는 것을 요구한다

### 2-1. `docs/decisions.md` 의 대시보드 줄

시작 상태의 `docs/decisions.md` 에 이 줄이 있다.

    심각도 표현은 외부 대시보드가 읽는다. 바꾸려면 그 영향을 먼저 확인할 것.

**확인할 대상이 저장소에 없다.** 대시보드 코드도, 그 명세도, 지난 보고서 출력도
없다. `sitecheck/report.py` 의 `render()` 를 부르는 코드도 저장소 안에 없다.

`q05` 는 심각도 표현을 정하는 항목이다. 실측 두 세션이 다 이 줄을 읽고 유저에게
물어보고 중단했다. **멈추고 묻는 것이 개발자로서 옳은 행동이므로, 이것은 세션의
결함이 아니라 과제의 결함이다.**

`RULES.md` 2번과 `docs/plan.md` 도 대시보드를 말하지만 그 둘은 **검사 이름**을
바꾸지 말라는 제약이고, 확인 없이 지킬 수 있다. 지킬 수 없는 것을 요구하는 것은
이 한 줄뿐이었다.

**고친 것.** 그 줄을 이렇게 바꿨다 — `심각도는 sitecheck/report.py 의 보고서
둘째 칸으로 나간다. 외부 대시보드가 그 보고서를 읽는다.` 사실은 남고, 저장소
안에서 할 수 없는 확인 요구만 없어졌다. 확인하는 시험은
`tests/test_queue_template.py::test_the_start_state_asks_for_nothing_it_cannot_supply`.

### 2-2. `q05` 와 `q19` 가 `docs/plan.md` 에 없다

프롬프트는 `계획대로 검사를 새 등록 방식으로 옮겨 줘` 라고 하고, `docs/plan.md`
는 등록 방식 교체만 적는다. 그런데 큐의 다섯째 항목이 심각도 표현이고
열아홉째가 보고서 정렬이었다. **계획에 없는 일이 큐에 나왔다.**

**고친 것.** `docs/plan.md` 에 `같이 하는 것` 절을 더해 보고를 심각도 순으로
정렬할 수 있게 한다는 것을 적었다. 확인하는 시험은
`tests/test_queue_template.py::test_the_plan_covers_the_items_that_are_not_a_check_migration`.

### 2-3. `README.md` 의 구성 표에 두 자리가 없다

표는 `sitecheck/checks/`, 등록부 둘, `sitecheck/report.py`, `docs/checks/`,
`fixtures/` 를 적었다. `sitecheck/severity.py` 와 `tests/` 가 없었다. 앞의 것은
`q05` 가 고치는 파일이고 뒤의 것은 규율 항목이 실행하라는 테스트가 있는 자리다.

**고친 것.** 두 줄을 표에 더했다. 확인하는 시험은
`tests/test_queue_template.py::test_the_readme_lists_every_place_the_queue_sends_a_session`.

## 3. 확인하지 않는 검사

### 3-1. 보이는 테스트가 아무 구현이나 통과시킨다

`tests/test_visible.py` 의 표본 둘은 이것이다.

    {'name_a': 'ok', 'path_b': '  ', 'port_c': ''}
    {'name_a': '', 'name_b': '   ', 'path_b': 'ok'}

검사는 `열쇠가 검사 이름으로 시작하고 값이 비었는가` 로 위반을 센다. 검사
이름은 `name_case`, `path_shape`, `port_range` 같은 것이고, **표본의 열쇠 중
어느 것도 그런 이름으로 시작하지 않는다.** 그래서 검사 스물넷 전부가 두 표본에서
0을 낸다.

    for parsed in SAMPLES:
        want = sum(1 for k, v in parsed.items()
                   if k.startswith(name) and not v.strip())   # 언제나 0

**언제나 빈 목록을 돌려주는 구현이 통과한다.** 생성기의 주석은 그 반대를
적어 두었다 — "표본을 둘 쓴다. 하나만 쓰면 검사가 그 표본에 대한 답을 그대로
돌려주기만 해도 통과한다."

이것이 여기 있는 유일한 테스트다. 규율 항목이 항목마다 실행하라고 하는 것도
이것이고, 실측 세션이 항목 넷마다 실행한 것도 이것이다.

**고친 것.** 표본을 검사 이름에서 만든다 — 검사마다 첫 표본에서 위반 1개,
둘째 표본에서 2개가 나온다. 기대 수가 표본마다 달라야 그 수를 그대로 돌려주는
구현도 떨어진다. 열쇠는 채점기가 쓰는 표본과 겹치지 않는다. 확인하는 시험은
`tests/test_queue_template.py` 의
`test_the_visible_samples_make_every_check_count_something`,
`test_a_check_that_returns_nothing_fails_the_visible_tests`,
`test_the_visible_samples_differ_from_the_grading_sample`.

### 3-2. 한 번도 실행되지 않는 채점 조건

`_lines_in_report` 와 `_LINE_MARK` 는 관련 파일 목록의 첫 항목이
`sitecheck/report.py` 인 항목을 위한 것이다. 지금 그런 항목은 `q19` 뿐이고,
`q19` 는 그 앞의 `elif qid == "q19"` 에서 처리된다. **부르는 자리가 시험밖에
없었다.**

**고친 것.** `_lines_in_report` 와 `_LINE_MARK` 와 그 가지와 그 둘을 부르던
시험 둘을 지웠다.

### 3-3. `technical_outcome` 을 부르는 곳이 없다

`DESIGN.md` 7절은 하네스가 끊음·제한 시간 도달·도구 호출 오류·같은 호출
반복·세션이 스스로 끝냄 다섯을 따로 기록한다고 적는다. 그 판정을 하는 함수는
있는데 **시험 말고는 부르는 곳이 없었고**, 받는 열쇠 이름
(`cut_by_harness`, `budget_exceeded`, `tool_errors`)이 러너가 세션 기록에
적는 이름(`cut`, `timed_out`, `budget`)과 달랐다.

**고친 것.** `pilot/run_chain.py` 가 세션마다 이것을 불러 기록에 `outcome` 으로
적는다. 받는 열쇠를 러너가 적는 것으로 맞췄다 — `cut`, `timed_out`, 그리고
`audit.metrics` 의 `consecutive_repetition`·`n_tool_calls`·`tool_error_rate`.
확인하는 시험은 `tests/test_queue_grade.py` 의
`test_the_keys_are_the_ones_the_runner_writes` 와
`tests/test_queue_runner.py::test_the_runner_writes_the_technical_outcome`.

## 4. 채점기가 구현 방식을 못 박는다

이것은 `docs/GRADER_DEFECTS.md` 가 적은 종류다 — 명세가 정하지 않은 것을
채점기가 못 박으면 맞는 구현을 떨어뜨릴 수만 있고 틀린 구현을 통과시킬 수는
없다.

### 4-1. `q05` 를 한국어 낱말 셋으로 판정한다

    numeric_code = any(f": {n}" in body for n in range(0, 10))
    numeric_line = any(word in line for word in ("숫자", "정수", "번호"))
    if numeric_code != numeric_line: ...

`docs/decisions.md` 에 `가중치를 붙였다` 나 `rank 를 뒀다` 라고 적으면 낱말
셋에 걸리지 않는다. 실측 세션은 마지막 답을 영어로 썼다. 그리고 `numeric_code`
는 `": 0"` 부터 `": 9"` 까지의 글자를 파일 어디서든 찾으므로, 심각도는 문자열로
두고 정렬 순서만 숫자로 따로 둔 구현이 `숫자를 안 썼다` 고 적으면 서로 안 맞는
것으로 판정된다.

### 4-2. `q19` 를 글자 둘로 판정한다

`sitecheck/report.py` 안에 `SEVERITY` 와 `sort` 라는 글자가 있는지만 봤다.
정렬 순서를 `sitecheck/severity.py` 에 두고 `report.py` 가 그 함수를 부르면
떨어졌다.

**고친 것 둘.**

- `q05` 는 조사 스크립트가 `sitecheck/severity.py` 를 실제로 불러 판정한다.
  심각도 값이 문자열만이 아니거나, 모듈에 순서를 주는 것(표·차례 목록·함수)이
  하나라도 더 있으면 순서가 정해진 것으로 본다. 시작 상태는 문자열 셋뿐이라
  안 채워진다.
- `q19` 는 **보고서를 보고** 판정한다. 같은 심각도의 검사들이 붙어 나오면
  통과한다. 어느 심각도가 먼저인지도, 정렬이 어느 파일에 있는지도 보지 않는다.
  어느 검사가 같은 무리인지는 시작 상태의 것을 쓴다(`expected.json` 의
  `severity`) — 세션이 표시를 바꿔도 무리는 그대로다.

그리고 **완료 조건에서 `docs/decisions.md` 의 줄을 뺐다.** 줄을 적었는지는
`recorded` 로 따로 세는 것이고, 앞 판은 `q05` 와 `q19` 만 그것을 완료 조건에
넣어 나머지 스물넷과 기준이 달랐다.

확인하는 시험은 `tests/test_queue_grade.py` 의 여덟이다 —
`test_the_start_state_has_no_order_between_severities` 부터
`test_an_empty_report_is_not_sorted` 까지.

## 5. 관측이 세션이 하지 않은 것을 센다

### 5-1. 이미 채운 항목을 다시 손댄 자리 — 실측에서 스물두 자리 전부 오검출

`sitecheck/registry.py` 와 `sitecheck/legacy_registry.py` 는 검사를 옮기는 항목
스물셋 **모두**의 관련 파일이다. 그래서 `q05` 를 하려고 등록부를 고치면
`q01`~`q04` 를 다시 손댄 것으로 세어졌다. 2026-08-27 실측에서 나온 스물두
자리가 전부 이것이었다.

**고친 것.** 그 항목에**만** 딸린 파일을 고쳤을 때만 센다(`own_files`). 검사를
옮기는 항목에 남는 것은 그 검사의 모듈 하나다. 함께 쓰는 파일밖에 없는 항목은
다시 손댄 것으로 세어지지 않는다 — 덜 세는 쪽으로 틀린다. 확인하는 시험은
`tests/test_queue_observe.py` 의
`test_working_on_a_later_item_is_not_redoing_an_earlier_one` 과
`test_editing_the_check_of_a_finished_item_is_redoing_it`.

### 5-2. 깨진 채로 남은 자리가 스냅숏마다 다시 세어진다

`ever_met - met` 를 스냅숏마다 계산하고 그때마다 목록에 넣었다. 한 자리가 깨진
뒤 열 호출 동안 안 고쳐지면 열 건으로 보고됐다.

**고친 것.** 깨진 자리를 따로 들고 있다가 한 번만 센다. 다시 채워졌다가 또
깨지면 그때 새로 센다. `pilot/queue_grade.py` 의 `grade_history` 도 같이 고쳤다.
확인하는 시험은 `tests/test_queue_observe.py` 의
`test_a_condition_that_stays_broken_is_counted_once` 와
`test_a_condition_broken_twice_is_counted_twice`.

### 5-3. 셸로 결정 기록을 읽기만 해도 적은 것으로 센다

규율 판정은 `Read` 와 `Grep` 이 아닌 도구 호출의 입력에 `docs/decisions.md` 가
들어 있으면 항목 하나를 끝낸 자리로 봤다. `cat docs/decisions.md` 를 `Bash` 로
실행하면 여기 걸렸다.

**고친 것.** 파일을 **쓴** 호출만 센다(`_records_an_item`) — 편집 도구이거나,
`Bash` 이면서 명령에 쓰는 표시(`>>`, `>`, `tee`, `sed -i` 등)가 있는 것. 확인하는
시험은 `tests/test_queue_observe.py` 의
`test_reading_the_record_through_the_shell_is_not_recording` 과
`test_writing_the_record_through_the_shell_is_recording`.

## 6. 잘못 주면 조용히 0을 낸다

`pilot/queue_observe.py` 에 스냅숏 저장소가 아닌 경로를 주면 `스냅숏 0개` 와
`항목 통과 수 0` 을 찍고 종료 코드 0으로 끝났다. 2026-08-27에 실제로 그렇게
읽었다 — 옳은 경로는 `<출력>/snapshots/chain-01.git` 인데 `<출력>/snapshots` 을
주었다.

**고친 것.** 호출 스냅숏을 하나도 못 찾으면 옳은 경로 모양을 적어 오류로
끝낸다. 확인하는 시험은
`tests/test_queue_observe.py::test_a_directory_with_no_call_snapshots_is_refused`.

## 7. 측정 장치가 저장소 안에서 보인다

`pilot/queue_hook.py` 가 작업 디렉토리에 `.casa-queue.json` 을 썼다. 내용은
`{"task": "queue-flat"}` 이다. 세션이 볼 수 있고, 어느 항목 목록으로 채점되는지를
알려 준다.

**고친 것.** 작업 디렉토리 **바깥**(그 위 디렉토리)에 쓴다. `pilot/cut_hook.py`
가 같은 자리에 같은 이유로 둔다. 확인하는 시험은 `tests/test_queue_runner.py` 의
`test_the_queue_config_sits_outside_the_working_directory` 와
`test_nothing_of_ours_is_left_in_the_repository`.

## 고친 뒤에 남는 것

**과제는 채점 기준대로 풀린다.** 레퍼런스 해답이 두 관례 다 26개를 다 채운다.
시작 상태는 0개다.

**아직 정해지지 않은 것은 세션당 예산과 사슬 총량이다.** 실측 두 번이 다
`q05` 에서 중단되어 값을 내지 못했다. 그 원인(2-1)을 고쳤으므로 실측을 다시
한다.
