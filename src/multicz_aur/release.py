# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Find a component's PKGBUILD, and the one it had at its last release."""

from __future__ import annotations

import subprocess
from pathlib import Path

from multicz.commits import latest_stable_tag, tag_prefix
from multicz.config import Config

from .pkgbuild import Pkgbuild, parse

PKGBUILD = "PKGBUILD"
SRCINFO = ".SRCINFO"


def package_dir(repo: Path, config: Config, component: str) -> Path | None:
    """The directory of ``component`` when it holds a PKGBUILD, relative to ``repo``.

    A component's ``paths`` are globs; the package directory is the one the
    first ``<dir>/**`` glob names. Components without a PKGBUILD are not AUR
    packages and are none of this plugin's business.
    """
    for pattern in config.components[component].paths:
        if pattern.endswith("/**"):
            candidate = Path(pattern.removesuffix("/**"))
            if (repo / candidate / PKGBUILD).is_file():
                return candidate
    return None


def aur_components(repo: Path, config: Config) -> dict[str, Path]:
    """Every component that is an AUR package, with its directory."""
    found = {}
    for name in config.components:
        directory = package_dir(repo, config, name)
        if directory is not None:
            found[name] = directory
    return found


def last_tag(repo: Path, config: Config, component: str) -> str | None:
    prefix = tag_prefix(config.tag_format_for(component), component)
    return latest_stable_tag(repo, prefix)


def read_at(repo: Path, ref: str, path: Path) -> str | None:
    """The content of ``path`` at ``ref``, or ``None`` when it did not exist."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path.as_posix()}"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


def released_pkgbuild(repo: Path, config: Config, component: str) -> Pkgbuild | None:
    """The PKGBUILD of ``component`` at its last release, if it has one."""
    directory = package_dir(repo, config, component)
    tag = last_tag(repo, config, component)
    if directory is None or tag is None:
        return None
    text = read_at(repo, tag, directory / PKGBUILD)
    return parse(text) if text is not None else None
