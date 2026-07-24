# ledger

A small layered money system. Amounts are integer minor units (cents)
throughout; the layers are:

- `money.py` — the `Money` value object
- `validation.py` — boundary checks
- `domain.py` — operations (`transfer`, `apply_fee`, `split_with_fee`)
- `serialize.py` — decimal formatting boundary
- `repository.py` — account store
- `api.py` — public entry points

`domain.split_with_fee` is the one operation not yet implemented. Each
module's docstring states the contract it participates in.

Run the tests with `python -m pytest`.
