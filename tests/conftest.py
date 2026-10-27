# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

import subprocess
from pathlib import Path

import pytest

PKGBUILD = """\
pkgname=demo
pkgver=1.0.0
pkgrel=1
depends=('glibc')
source=("https://example.org/demo-$pkgver.tar.gz")
sha256sums=('aaaa')

build() {
  make
}
"""

SRCINFO = """\
pkgbase = demo
\tpkgver = 1.0.0
\tpkgrel = 1
\tdepends = glibc
\tsource = https://example.org/demo-1.0.0.tar.gz
\tsha256sums = aaaa

pkgname = demo
"""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def write(repo: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def commit(repo: Path, message: str, files: dict[str, str]) -> None:
    write(repo, files)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    return tmp_path
