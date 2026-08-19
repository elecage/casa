"""Alarm rules (docs/ALARM_RULE.md — pre-registered 2026-08-19).

Seven named rules, each with its own alert and stop-recommendation threshold.
Not a weighted score: weights would have to be fitted, fitting means looking
at the data first, and that turns a finding into an artefact of tuning. Named
rules have nothing to fit. They also give the reader something to act on —
"the same command 4 times in a row" rather than "0.73" — and an external app's
only lever is telling a person (docs/ARCHITECTURE.md).

Thresholds come from published measurements, not from this project's data:
successful recovery takes a median of 5 steps and failed recovery 12, so a
standstill of 5 has already spent a typical recovery and 12 has reached the
length of one that failed.

**Do not retune these here.** Changing a threshold means editing
docs/ALARM_RULE.md and recording why and when in the STATUS.md decision log.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .metrics import _is_aux_check, _is_test_run, _normalized_key
from .progress import ProgressTracker
from .transcript import Session, ToolCall

ALERT = "alert"
STOP = "stop"

# Calls at the very start, and just after a compaction, are exempt: there is
# not enough history to judge, and compaction resets the knowledge memory.
WARMUP_CALLS = 3

# (alert, stop). None means the rule never recommends stopping.
THRESHOLDS: dict[str, tuple[int, int | None]] = {
    "R1_standstill": (5, 12),
    "R2_identical_calls": (3, 6),
    "R3_action_cycle": (2, 3),
    "R4_evidence_stall": (3, 6),
    "R5_error_ignored": (3, 5),
    "R6_reverts": (3, 5),
    "R7_survey_paralysis": (30, None),
}


@dataclass
class Firing:
    rule: str
    level: str          # ALERT or STOP
    value: int          # the count that tripped it
    message: str        # specific enough for a person to act on


@dataclass
class AlarmSnapshot:
    index: int
    firings: list[Firing] = field(default_factory=list)

    @property
    def alerting(self) -> bool:
        return bool(self.firings)

    @property
    def stop_recommended(self) -> bool:
        """A rule at its stop threshold, or two different rules alerting.

        The second arm is a vote with no weights, so there is nothing to fit.
        """
        if any(f.level == STOP for f in self.firings):
            return True
        return len({f.rule for f in self.firings}) >= 2

    def describe(self) -> str:
        return " / ".join(f.message for f in self.firings)


def _cycle_repeats(keys: list[str], min_len: int = 3) -> int:
    """How many times the trailing block repeats back to back."""
    best = 0
    for size in range(min_len, len(keys) // 2 + 1):
        block = keys[-size:]
        count = 1
        pos = len(keys) - size
        while pos - size >= 0 and keys[pos - size:pos] == block:
            count += 1
            pos -= size
        if count >= 2:
            best = max(best, count)
    return best


@dataclass
class AlarmMonitor:
    """Streaming alarm state. Feed calls in order; never looks ahead."""

    tracker: ProgressTracker = field(default_factory=ProgressTracker)
    # rule counters
    _standstill_run: int = 0
    _identical_run: int = 0
    _error_ignored_run: int = 0
    _evidence_stall: int = 0
    _reverts: int = 0
    _keys: list[str] = field(default_factory=list)
    _saw_artifact: bool = False
    _prev_key: str | None = None
    _prev_error: bool = False
    _last_compaction_at: int = -10_000
    _compactions: int = 0
    # first time each rule reached each level — the analysis anchor, never
    # cleared even when the live alert goes away
    first_alert: dict[str, int] = field(default_factory=dict)
    first_stop: dict[str, int] = field(default_factory=dict)

    def observe(self, call: ToolCall) -> AlarmSnapshot:
        verdict = self.tracker.observe(call)
        key = _normalized_key(call)

        if call.after_compaction > self._compactions:
            self._compactions = call.after_compaction
            self._last_compaction_at = call.index

        # --- counters ---------------------------------------------------
        self._standstill_run = (
            self._standstill_run + 1 if verdict.is_standstill else 0)

        self._identical_run = (
            self._identical_run + 1 if key == self._prev_key else 1)

        if self._prev_error and key == self._prev_key:
            self._error_ignored_run += 1
        else:
            self._error_ignored_run = 0

        if verdict.artifact > 0:
            self._saw_artifact = True
        if verdict.artifact < 0:
            self._reverts += 1

        if _is_test_run(call) or _is_aux_check(call):
            if verdict.evidence > 0:
                self._evidence_stall = 0
            elif self._saw_artifact:
                self._evidence_stall += 1

        self._keys.append(key)
        self._prev_key, self._prev_error = key, call.is_error

        snapshot = AlarmSnapshot(index=call.index)
        if self._suppressed(call):
            return snapshot

        self._check("R1_standstill", self._standstill_run, snapshot,
                    "{v}번째 호출째 새로 읽은 것도, 바뀐 파일도, "
                    "달라진 확인 결과도 없습니다")
        self._check("R2_identical_calls", self._identical_run, snapshot,
                    "같은 명령을 연속 {v}번 실행했습니다")
        self._check("R3_action_cycle", _cycle_repeats(self._keys), snapshot,
                    "같은 행동 묶음을 {v}번 되풀이하고 있습니다")
        self._check("R4_evidence_stall", self._evidence_stall, snapshot,
                    "고친 뒤 확인을 {v}번 했는데 결과가 그대로입니다")
        self._check("R5_error_ignored", self._error_ignored_run, snapshot,
                    "에러가 난 뒤 같은 명령을 {v}번 반복했습니다")
        self._check("R6_reverts", self._reverts, snapshot,
                    "고쳤다 되돌리기를 {v}번 했습니다")
        if not self._saw_artifact:
            self._check("R7_survey_paralysis", call.index + 1, snapshot,
                        "{v}번 호출하는 동안 아직 아무것도 고치지 않았습니다")
        return snapshot

    # -- internals -------------------------------------------------------

    def _suppressed(self, call: ToolCall) -> bool:
        if call.index < WARMUP_CALLS:
            return True
        return call.index - self._last_compaction_at < WARMUP_CALLS

    def _check(self, rule: str, value: int, snapshot: AlarmSnapshot,
               template: str) -> None:
        alert_at, stop_at = THRESHOLDS[rule]
        if stop_at is not None and value >= stop_at:
            level = STOP
        elif value >= alert_at:
            level = ALERT
        else:
            return
        snapshot.firings.append(
            Firing(rule=rule, level=level, value=value,
                   message=template.format(v=value)))
        self.first_alert.setdefault(rule, snapshot.index)
        if level == STOP:
            self.first_stop.setdefault(rule, snapshot.index)


def alarm_series(session: Session) -> list[AlarmSnapshot]:
    monitor = AlarmMonitor()
    return [monitor.observe(call) for call in session.tool_calls]


def alarm_summary(session: Session) -> dict:
    """Per-session roll-up for the restart evaluation.

    `tau_alert` / `tau_stop` are the anchors docs/RESTART_EVALUATION.md needs:
    the first call at which the alarm would have fired, regardless of whether
    it later cleared.
    """
    monitor = AlarmMonitor()
    snapshots = [monitor.observe(call) for call in session.tool_calls]

    alerting = [s for s in snapshots if s.alerting]
    stopping = [s for s in snapshots if s.stop_recommended]
    n = len(snapshots)
    return {
        "n_calls": n,
        "ever_alerted": bool(alerting),
        "ever_stop_recommended": bool(stopping),
        "tau_alert": alerting[0].index if alerting else None,
        "tau_stop": stopping[0].index if stopping else None,
        "alert_cleared": bool(alerting) and not snapshots[-1].alerting,
        "alerting_calls": len(alerting),
        "first_alert_by_rule": dict(monitor.first_alert),
        "first_stop_by_rule": dict(monitor.first_stop),
        "first_alert_position": (alerting[0].index / n) if alerting and n else None,
    }
