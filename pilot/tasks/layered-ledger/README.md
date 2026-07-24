# layered-ledger — architectural-complexity task (W13)

Design spec: `docs/ARCH_TASK_DESIGN.md`. This task carries the **달성·
조기판별** (achievement + early-detection) axis after orbit's baseline
showed its discriminating signal was late (a single-file numerical puzzle
artefact). Here the discriminating behavior is **surveying the modules a
change must respect before editing** — an early, architecture-native
signal (`coverage_before_first_edit`).

## Structure

- `template/` — a working layered money ledger (money → validation →
  domain → serialize → repository → api). Amounts are integer minor units
  throughout. One operation, `domain.split_with_fee`, is unimplemented.
- `hidden_tests/test_contract.py` — never shipped; enforces the
  cross-cutting invariants the visible suite avoids.
- `solution/src/ledger/domain.py` — reference (passes visible + hidden).
- `calibration/naive_domain.py` — a naive split that passes visible, fails
  hidden; used to prove the oracle separates careless from careful.

## The cross-cutting contract (spans modules, not stated in one place)

1. Amounts stay in **integer minor units** everywhere; formatting is only
   at `serialize.py`. (money.py)
2. When a division yields a fractional cent, round at **one** place —
   `domain.round_half_even` (banker's rounding). No second rounding, no
   floats. `apply_fee` is the worked example. (domain.py)
3. Every externally supplied amount passes the **validation gate** before a
   domain op uses it. (validation.py)

`split_with_fee` must thread a new fee-bearing split through all three.
Its docstring states only the conservation contract; the rounding rule and
the validation gate must be discovered by reading the modules — so a
session that dives straight into `domain.py` without surveying the layers
tends to lose remainder cents, leak floats, or skip validation, passing the
visible tests while failing the hidden suite.

## Failure modes the hidden suite catches

- **Remainder loss**: `total // n` for every share drops the remainder →
  principal not conserved (e.g. 100.00 / 3).
- **Float leakage**: `total.minor / n` returns floats → type + conservation
  failures.
- **Wrong / double rounding**: fees not matching the single banker's-rounding
  point.
- **Validation bypass**: negative principal, non-positive `n`, or out-of-range
  rate not rejected.

Grading is fully deterministic (integer comparisons; no tolerance tuning,
unlike orbit).

## Failure-band knobs (set by calibration, not guessed)

- number of layers the change must respect (default: 4),
- discoverability of the invariant (default: not stated in the split
  docstring; found by reading the code),
- number of remainder/rounding edge cases in the hidden suite.

**Calibration status:** reference and naive checks pinned by
`tests/test_layered_ledger_task.py`. Success-rate calibration (sonnet 2–3
sessions, target 20–80% + `coverage_before_first_edit` spread) is the next
gate before collection; adjust the knobs above if saturated.
