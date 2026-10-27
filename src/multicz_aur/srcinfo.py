# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Keep the version lines of a generated ``.SRCINFO`` in step with its PKGBUILD.

``.SRCINFO`` is produced by ``makepkg --printsrcinfo`` and must agree with the
PKGBUILD. A release only moves ``pkgver`` and ``pkgrel``, so those two lines can
be rewritten in place without running makepkg, which only exists on Arch.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from .pkgbuild import Pkgbuild

_FIELDS = ("pkgver", "pkgrel")


def _line(field: str) -> re.Pattern[str]:
    return re.compile(rf"^(?P<head>[ \t]*{field} = )(?P<value>.*?)[ \t]*$", re.MULTILINE)


def _replacement(value: str) -> Callable[[re.Match[str]], str]:
    def replace(match: re.Match[str]) -> str:
        return match.group("head") + value

    return replace


def read(text: str) -> dict[str, str]:
    """Return the ``pkgver`` and ``pkgrel`` found in the first (pkgbase) section."""
    found: dict[str, str] = {}
    for field in _FIELDS:
        match = _line(field).search(text)
        if match:
            found[field] = match.group("value")
    return found


def sync(text: str, pkgver: str, pkgrel: str) -> str:
    """Rewrite the ``pkgver`` and ``pkgrel`` lines of ``text``."""
    for field, value in (("pkgver", pkgver), ("pkgrel", pkgrel)):
        pattern = _line(field)
        if not pattern.search(text):
            raise KeyError(field)
        text = pattern.sub(_replacement(value), text, count=1)
    return text


def mismatches(text: str, pkgbuild: Pkgbuild) -> list[str]:
    """Describe where ``.SRCINFO`` disagrees with the PKGBUILD on the two versions."""
    srcinfo = read(text)
    problems = []
    for field in _FIELDS:
        expected = pkgbuild.scalar(field)
        actual = srcinfo.get(field)
        if expected is None or actual == expected:
            continue
        problems.append(f"{field} is {actual!r} in .SRCINFO but {expected!r} in the PKGBUILD")
    return problems
