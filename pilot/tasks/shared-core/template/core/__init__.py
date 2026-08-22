"""What both products share.

`opsbox` (operations) and `billsy` (billing) both read the same usage records
and both have to agree on four things: how a timestamp is read, where the
month boundary goes, how an account name is spelled, and how money is rounded.

**Those four live here and nowhere else.** When they lived inside one product
the other product grew its own copy, and the two copies drifted without any
error being raised. `README.md` has the dependency table.
"""
