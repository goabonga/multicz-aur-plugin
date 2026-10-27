# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

import pytest

from multicz_aur.pkgbuild import parse
from multicz_aur.srcinfo import mismatches, read, sync

SRCINFO = """\
pkgbase = demo
\tpkgdesc = A demo
\tpkgver = 1.2.3
\tpkgrel = 2
\tarch = x86_64
\tdepends = glibc
\tsource = demo::git+https://example.org/demo.git#commit=abc

pkgname = demo
"""


def test_read_finds_the_versions_of_the_pkgbase_section():
    assert read(SRCINFO) == {"pkgver": "1.2.3", "pkgrel": "2"}


def test_read_ignores_what_is_not_there():
    assert read("pkgbase = demo\n") == {}


def test_sync_rewrites_only_the_two_lines():
    out = sync(SRCINFO, "2.0.0", "1")
    assert "\tpkgver = 2.0.0\n" in out
    assert "\tpkgrel = 1\n" in out
    assert out.replace("2.0.0", "1.2.3").replace("pkgrel = 1", "pkgrel = 2") == SRCINFO


def test_sync_keeps_the_tab_indentation_and_trailing_text():
    assert sync(SRCINFO, "9", "9").count("\t") == SRCINFO.count("\t")


def test_sync_is_idempotent():
    once = sync(SRCINFO, "2.0.0", "1")
    assert sync(once, "2.0.0", "1") == once


def test_sync_refuses_a_srcinfo_without_the_field():
    with pytest.raises(KeyError, match="pkgrel"):
        sync("pkgbase = demo\n\tpkgver = 1\n", "2", "1")


def test_mismatches_reports_each_disagreement():
    pkgbuild = parse("pkgver=2.0.0\npkgrel=1\n")
    assert mismatches(SRCINFO, pkgbuild) == [
        "pkgver is '1.2.3' in .SRCINFO but '2.0.0' in the PKGBUILD",
        "pkgrel is '2' in .SRCINFO but '1' in the PKGBUILD",
    ]


def test_mismatches_is_empty_when_they_agree():
    assert mismatches(SRCINFO, parse("pkgver=1.2.3\npkgrel=2\n")) == []


def test_mismatches_skips_what_the_pkgbuild_does_not_state():
    assert mismatches(SRCINFO, parse("pkgname=demo\n")) == []
