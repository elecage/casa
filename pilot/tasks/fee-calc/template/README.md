# feecalc

A progressive transaction-fee calculator: a flat base fee plus marginal
tier rates, like marginal income tax. The public API is `feecalc.fee`.

The full fee contract is documented in the `fee` docstring
(`src/feecalc/fees.py`). Run the tests with `python -m pytest`.
