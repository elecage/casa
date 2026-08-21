"""The one place account spelling is normalized. The spec is the "Account
spelling" section of `docs/ingest.md`.

**Why it is separate.** All six adapters use it, and archiving and cleanup
(subsystem D) has to use the same rule when it picks files. Once the rule
lives in two places, one of them quietly leaves files it could not pick.
"""

from __future__ import annotations


def normalize_account(raw: str) -> str:
    """Normalize the spelling of an account name.

    Right now this only strips the surrounding whitespace. The same account
    arrives with different case depending on the source (`acme-01`,
    `ACME-01`), and nothing has been decided about that yet.
    """
    return raw.strip()
