"""Reference solution for the config-parser task (grading/calibration only,
never shipped to sessions). Implements the parse() contract as a small
character-level state machine."""

from __future__ import annotations

_DQUOTE_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}


def _join_continuations(text: str) -> list[str]:
    """Merge physical lines ending in an odd number of backslashes."""
    logical: list[str] = []
    buffer = ""
    for physical in text.split("\n"):
        trailing = len(physical) - len(physical.rstrip("\\"))
        if trailing % 2 == 1:
            buffer += physical[:-1]
        else:
            logical.append(buffer + physical)
            buffer = ""
    if buffer:
        logical.append(buffer)
    return logical


def _parse_value(raw: str) -> str:
    i = 0
    n = len(raw)
    while i < n and raw[i] in " \t":
        i += 1
    if i < n and raw[i] == '"':
        i += 1
        out = []
        while i < n:
            c = raw[i]
            if c == "\\" and i + 1 < n and raw[i + 1] in _DQUOTE_ESCAPES:
                out.append(_DQUOTE_ESCAPES[raw[i + 1]])
                i += 2
                continue
            if c == '"':
                break
            out.append(c)
            i += 1
        return "".join(out)
    if i < n and raw[i] == "'":
        i += 1
        out = []
        while i < n and raw[i] != "'":
            out.append(raw[i])
            i += 1
        return "".join(out)
    # unquoted: to end or unquoted '#', strip surrounding whitespace
    end = raw.find("#", i)
    body = raw[i:] if end == -1 else raw[i:end]
    return body.strip()


def parse(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    section: str | None = None
    for line in _join_continuations(text):
        stripped = line.strip()
        if not stripped or stripped[0] == "#":
            continue
        if stripped[0] == "[" and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            continue
        eq = line.find("=")
        if eq == -1:
            continue
        key = line[:eq].strip()
        value = _parse_value(line[eq + 1:])
        result[f"{section}.{key}" if section else key] = value
    return result
