# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Tell what a PKGBUILD edit does to the package, and what ``pkgrel`` must follow.

Two kinds of edit look alike in a diff and are very different for pacman:

* the **source** moved: a new ``pkgver``, a new source URL or commit, new
  checksums. It is new upstream content, and ``pkgrel`` starts again at ``1``;
* the **configuration** moved: dependencies, build flags, install paths. The
  upstream content is the same, so ``pkgrel`` counts one more revision.

Anything else (comments, whitespace, ``pkgrel`` itself) changes nothing the user
installs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from .pkgbuild import Pkgbuild, expand

_CHECKSUMS = re.compile(r"^(?:md5|sha1|sha224|sha256|sha384|sha512|b2|cksum)sums(?:_\w+)?$")
_SOURCES = re.compile(r"^source(?:_\w+)?$")


class Change(StrEnum):
    NONE = "none"
    CONFIG = "config"
    SOURCE = "source"


@dataclass(frozen=True)
class Diff:
    change: Change
    pkgver_changed: bool = False
    source_changed: bool = False
    checksums_changed: bool = False
    reasons: list[str] = field(default_factory=list)


def classify(old: Pkgbuild, new: Pkgbuild) -> Diff:
    """Compare ``new`` against ``old``, the PKGBUILD of the previous release."""
    pkgver_changed = (old.scalar("pkgver"), old.scalar("epoch")) != (
        new.scalar("pkgver"),
        new.scalar("epoch"),
    )
    source_changed = _sources(old) != _sources(new)
    checksums_changed = _checksums(old) != _checksums(new)
    reasons = []
    if pkgver_changed:
        reasons.append(f"pkgver {old.scalar('pkgver')} -> {new.scalar('pkgver')}")
    if source_changed:
        reasons.append("source changed")
    if checksums_changed:
        reasons.append("checksums changed")
    if reasons:
        change = Change.SOURCE
    elif _configuration(old) != _configuration(new):
        change, reasons = Change.CONFIG, ["configuration changed"]
    else:
        change = Change.NONE
    return Diff(change, pkgver_changed, source_changed, checksums_changed, reasons)


def next_pkgrel(old: Pkgbuild, new: Pkgbuild) -> str:
    """The ``pkgrel`` ``new`` must carry, whatever it says today.

    Computed from the previous release rather than from the edited file, so it
    does not depend on whether someone already touched ``pkgrel`` by hand.
    """
    previous = old.scalar("pkgrel") or "1"
    if not previous.isdecimal():
        raise ValueError(f"pkgrel {previous!r} of the previous release is not an integer")
    diff = classify(old, new)
    if diff.pkgver_changed:
        return "1"
    if diff.change is Change.NONE:
        return previous
    return str(int(previous) + 1)


def _sources(pkgbuild: Pkgbuild) -> dict[str, list[str]]:
    scalars = pkgbuild.scalars
    return {
        name: [expand(item, scalars) for item in pkgbuild.array(name)]
        for name in pkgbuild.assignments
        if _SOURCES.match(name)
    }


def _checksums(pkgbuild: Pkgbuild) -> dict[str, list[str]]:
    return {n: pkgbuild.array(n) for n in pkgbuild.assignments if _CHECKSUMS.match(n)}


def _configuration(pkgbuild: Pkgbuild) -> list[str]:
    """What the script does, ignoring comments, spacing, order and the version lines.

    Assignments are compared by value, so ``( 'a' )`` equals ``('a')``; the rest
    of the script (functions and so on) is compared line by line.
    """
    text = pkgbuild.text
    assignments = []
    spans = []
    for name, found in pkgbuild.assignments.items():
        spans.append((found.start - len(name) - 1, found.end))
        if name not in ("pkgver", "pkgrel"):
            assignments.append(f"{name}={found.value!r}")
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + text[end:]
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(re.sub(r"\s+", " ", line))
    return sorted(assignments) + lines
