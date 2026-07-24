"""minicfg configuration parser.

``parse`` is the public API and is not implemented yet. The test suite
currently fails.

Parsing contract for parse(text) -> dict[str, str]
--------------------------------------------------
The input is a configuration file as a string. ``parse`` returns a flat
dict mapping fully-qualified keys to their string values. The grading
reference for this repository enforces the whole contract; the bundled
test suite exercises only a small part of it.

Structure
- Lines are separated by ``\\n``. Blank lines are ignored.
- A line whose first non-whitespace character is ``#`` is a comment and
  is ignored.
- A line of the form ``[name]`` (after stripping surrounding whitespace)
  opens a section. Subsequent keys are qualified as ``name.key``. Keys
  before any section header are stored under their bare name.
- Every other non-blank line is ``key = value``. The key is the text up
  to the first unquoted ``=``, stripped of surrounding whitespace. When a
  key is repeated, the last assignment wins.

Values
- An unquoted value runs to the end of the logical line, except that an
  unquoted ``#`` begins an inline comment and is discarded. Surrounding
  whitespace is stripped from an unquoted value.
- A value may instead be wrapped in double quotes ``"..."`` or single
  quotes ``'...'``. Quoting preserves leading and trailing whitespace and
  makes ``#`` inside the value literal (not an inline comment).
- Inside double quotes, the escape sequences ``\\n`` (newline), ``\\t``
  (tab), ``\\\\`` (backslash), and ``\\"`` (double quote) are recognised.
- Single quotes are literal: no escape processing. A backslash inside
  single quotes is a backslash.
- After a closing quote, any remaining whitespace and an optional inline
  ``#`` comment are ignored.

Line continuation
- A logical line may span several physical lines: if a physical line ends
  with an odd number of backslashes, the final backslash and the newline
  are removed and the next physical line is appended (concatenated, with
  no separator added). An even number of trailing backslashes does not
  continue the line.
"""

from __future__ import annotations


def parse(text: str) -> dict[str, str]:
    """Parse ``text`` into a flat ``{key: value}`` dict per the module
    contract."""
    raise NotImplementedError("parse is not implemented yet")
