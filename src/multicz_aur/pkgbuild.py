# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Read and edit a PKGBUILD without ever executing it.

A PKGBUILD is a bash script, and in CI it comes from a pull request, so it
must never be sourced. This module scans the text instead and only
understands what a package needs to say statically: top-level ``name=value``
and ``name=(a b c)`` assignments, with the usual quoting. Function bodies
are skipped, and so is anything it does not recognise: a value that cannot
be read statically is simply absent, never guessed.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field

_ASSIGN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=")
_FUNCTION = re.compile(r"[A-Za-z_][\w:.-]*\s*\(\)\s*\{?")
_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


@dataclass(frozen=True)
class Assignment:
    """One top-level assignment, with where its value sits in the text."""

    name: str
    value: str | list[str]
    line: int
    start: int
    end: int
    quote: str = ""


@dataclass
class Pkgbuild:
    text: str
    assignments: dict[str, Assignment] = field(default_factory=dict)

    def scalar(self, name: str) -> str | None:
        found = self.assignments.get(name)
        return found.value if found and isinstance(found.value, str) else None

    def array(self, name: str) -> list[str]:
        found = self.assignments.get(name)
        if found is None:
            return []
        return list(found.value) if isinstance(found.value, list) else [found.value]

    @property
    def scalars(self) -> dict[str, str]:
        return {n: a.value for n, a in self.assignments.items() if isinstance(a.value, str)}


def parse(text: str) -> Pkgbuild:
    """Collect the top-level assignments of ``text``. The first one of a name wins."""
    result = Pkgbuild(text=text)
    pos = 0
    while pos < len(text):
        line_end = text.find("\n", pos)
        line_end = len(text) if line_end == -1 else line_end
        line = text[pos:line_end]
        assign = _ASSIGN.match(line)
        if assign:
            parsed = _read_assignment(text, pos, assign)
            if parsed is not None:
                result.assignments.setdefault(parsed.name, parsed)
                pos = parsed.end
                continue
        elif _FUNCTION.match(line):
            pos = _skip_function(text, pos)
            continue
        pos = line_end + 1
    return result


def set_scalar(text: str, name: str, value: str) -> str:
    """Replace the value of the top-level scalar ``name``, keeping its quoting."""
    found = parse(text).assignments.get(name)
    if found is None or not isinstance(found.value, str):
        raise KeyError(name)
    return text[: found.start] + f"{found.quote}{value}{found.quote}" + text[found.end :]


def expand(value: str, scalars: dict[str, str]) -> str:
    """Substitute ``$name`` and ``${name}`` for known scalars, leaving the rest as is."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        return scalars.get(name, match.group(0))

    previous = None
    while previous != value:
        previous, value = value, _VAR.sub(replace, value)
    return value


def _read_assignment(text: str, line_start: int, assign: re.Match[str]) -> Assignment | None:
    name = assign.group(1)
    value_start = line_start + assign.end()
    line = text.count("\n", 0, line_start) + 1
    if text.startswith("(", value_start):
        end = _matching_paren(text, value_start)
        if end is None:
            return None
        inner = text[value_start + 1 : end]
        try:
            items = shlex.split(inner, comments=True)
        except ValueError:
            return None
        return Assignment(name, items, line, value_start, end + 1)
    end, quote, raw = _scan_word(text, value_start)
    try:
        parts = shlex.split(raw)
    except ValueError:
        return None
    value = parts[0] if parts else ""
    return Assignment(name, value, line, value_start, end, quote)


def _scan_word(text: str, start: int) -> tuple[int, str, str]:
    """Return ``(end, quote, raw)`` of the shell word starting at ``start``.

    ``quote`` is the quote character when the whole word is one quoted string.
    """
    i = start
    quote = ""
    if start < len(text) and text[start] in "'\"":
        quote = text[start]
    in_single = in_double = False
    while i < len(text):
        c = text[i]
        if in_single:
            in_single = c != "'"
        elif in_double:
            if c == "\\":
                i += 1
            elif c == '"':
                in_double = False
        elif c == "'":
            in_single = True
        elif c == '"':
            in_double = True
        elif c in " \t\n;":
            break
        i += 1
    raw = text[start:i]
    if quote and not (len(raw) >= 2 and raw.endswith(quote) and raw.count(quote) == 2):
        quote = ""
    return i, quote, raw


def _matching_paren(text: str, start: int) -> int | None:
    depth = 0
    in_single = in_double = in_comment = False
    i = start
    while i < len(text):
        c = text[i]
        if in_comment:
            in_comment = c != "\n"
        elif in_single:
            in_single = c != "'"
        elif in_double:
            if c == "\\":
                i += 1
            elif c == '"':
                in_double = False
        elif c == "'":
            in_single = True
        elif c == '"':
            in_double = True
        elif c == "#" and (i == 0 or text[i - 1] in " \t\n"):
            in_comment = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _skip_function(text: str, start: int) -> int:
    """Return the offset just past the function whose header starts at ``start``."""
    depth = 0
    seen_open = False
    in_single = in_double = in_comment = False
    i = start
    while i < len(text):
        c = text[i]
        if in_comment:
            in_comment = c != "\n"
        elif in_single:
            in_single = c != "'"
        elif in_double:
            if c == "\\":
                i += 1
            elif c == '"':
                in_double = False
        elif c == "'":
            in_single = True
        elif c == '"':
            in_double = True
        elif c == "#" and (i == 0 or text[i - 1] in " \t\n"):
            in_comment = True
        elif c == "{":
            depth += 1
            seen_open = True
        elif c == "}":
            depth -= 1
            if seen_open and depth == 0:
                end = text.find("\n", i)
                return len(text) if end == -1 else end + 1
        i += 1
    return len(text)
