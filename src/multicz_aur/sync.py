# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Apply the ``pkgrel`` rule to a package, and carry it into ``.SRCINFO``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from multicz.config import Config

from . import srcinfo
from .classify import next_pkgrel
from .pkgbuild import parse, set_scalar
from .release import PKGBUILD, SRCINFO, package_dir, released_pkgbuild


class SyncError(Exception):
    """The package cannot be synchronised; the message says why."""


@dataclass(frozen=True)
class SyncResult:
    component: str
    pkgver: str
    pkgrel_before: str | None
    pkgrel_after: str
    first_release: bool
    pkgbuild_changed: bool
    srcinfo_changed: bool


def sync_component(repo: Path, config: Config, component: str, *, write: bool = True) -> SyncResult:
    """Set ``pkgrel`` from the last release and bring ``.SRCINFO`` in line.

    With ``write=False`` nothing is touched and the result says what would be.
    """
    if component not in config.components:
        raise SyncError(f"unknown component {component!r}")
    directory = package_dir(repo, config, component)
    if directory is None:
        raise SyncError(f"component {component!r} has no {PKGBUILD} under its paths")

    pkgbuild_path = repo / directory / PKGBUILD
    text = pkgbuild_path.read_text(encoding="utf-8")
    current = parse(text)
    pkgver = current.scalar("pkgver")
    if pkgver is None:
        raise SyncError(f"{directory / PKGBUILD} has no readable pkgver")

    released = released_pkgbuild(repo, config, component)
    before = current.scalar("pkgrel")
    try:
        after = next_pkgrel(released, current) if released is not None else (before or "1")
    except ValueError as exc:
        raise SyncError(str(exc)) from exc

    new_text = text if before == after else _set_pkgrel(text, after, directory)
    srcinfo_path = repo / directory / SRCINFO
    old_srcinfo = srcinfo_path.read_text(encoding="utf-8") if srcinfo_path.is_file() else None
    try:
        new_srcinfo = srcinfo.sync(old_srcinfo, pkgver, after) if old_srcinfo is not None else None
    except KeyError as exc:
        raise SyncError(f"{directory / SRCINFO} has no {exc.args[0]} line") from exc

    if write:
        if new_text != text:
            pkgbuild_path.write_text(new_text, encoding="utf-8")
        if new_srcinfo is not None and new_srcinfo != old_srcinfo:
            srcinfo_path.write_text(new_srcinfo, encoding="utf-8")
    return SyncResult(
        component=component,
        pkgver=pkgver,
        pkgrel_before=before,
        pkgrel_after=after,
        first_release=released is None,
        pkgbuild_changed=new_text != text,
        srcinfo_changed=new_srcinfo is not None and new_srcinfo != old_srcinfo,
    )


def _set_pkgrel(text: str, value: str, directory: Path) -> str:
    try:
        return set_scalar(text, "pkgrel", value)
    except KeyError as exc:
        raise SyncError(f"{directory / PKGBUILD} has no top-level pkgrel to update") from exc
