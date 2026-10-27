# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""``multicz-aur``: the command a component's ``post_bump`` hook runs."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from multicz.config import find_config, load_config

from .sync import SyncError, sync_component


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="multicz-aur", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser(
        "sync",
        help="set pkgrel from the last release and bring .SRCINFO in line",
    )
    sync.add_argument("component", help="the multicz component, which is the package name")
    sync.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args(argv)

    try:
        config_path = find_config(Path.cwd())
        config = load_config(config_path)
        result = sync_component(config_path.parent, config, args.component, write=not args.dry_run)
    except (FileNotFoundError, ValueError, SyncError) as exc:
        print(f"multicz-aur: {exc}", file=sys.stderr)
        return 1

    verb = "would set" if args.dry_run else "set"
    note = " (first release)" if result.first_release else ""
    print(
        f"{result.component}: pkgver {result.pkgver}, {verb} pkgrel "
        f"{result.pkgrel_before} -> {result.pkgrel_after}{note}",
        file=sys.stderr,
    )
    return 0
