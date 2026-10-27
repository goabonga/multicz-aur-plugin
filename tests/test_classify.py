# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

import pytest

from multicz_aur.classify import Change, classify, next_pkgrel
from multicz_aur.pkgbuild import parse

BASE = """\
# Maintainer: Chris
pkgname=demo
pkgver=1.0.0
pkgrel=3
_commit=abc
depends=('glibc')
source=("${pkgname}::git+https://example.org/demo.git#commit=${_commit}")
sha256sums=('SKIP')

build() {
  make
}
"""


def edit(old: str, new: str) -> str:
    assert old in BASE, old
    return BASE.replace(old, new, 1)


def diff(text: str):
    return classify(parse(BASE), parse(text))


def test_identical_files_change_nothing():
    assert diff(BASE).change is Change.NONE


@pytest.mark.parametrize(
    "text",
    [
        BASE.replace("# Maintainer: Chris", "# Maintainer: Someone Else"),
        BASE + "\n\n# trailing comment\n",
        BASE.replace("depends=('glibc')", "depends=(  'glibc'  )"),
        edit("pkgrel=3", "pkgrel=9"),
    ],
)
def test_comments_spacing_and_pkgrel_are_not_changes(text: str):
    assert diff(text).change is Change.NONE


@pytest.mark.parametrize(
    "text",
    [
        edit("depends=('glibc')", "depends=('glibc' 'zlib')"),
        edit("  make", "  make -j1"),
        edit("build() {", "prepare() {\n  true\n}\n\nbuild() {"),
    ],
)
def test_configuration_edits_are_config_changes(text: str):
    result = diff(text)
    assert result.change is Change.CONFIG
    assert not result.pkgver_changed
    assert result.reasons == ["configuration changed"]


def test_a_new_pkgver_is_a_source_change():
    result = diff(edit("pkgver=1.0.0", "pkgver=1.1.0"))
    assert result.change is Change.SOURCE
    assert result.pkgver_changed
    assert result.reasons == ["pkgver 1.0.0 -> 1.1.0"]


def test_a_new_pinned_commit_is_a_source_change_through_the_variable():
    result = diff(edit("_commit=abc", "_commit=def"))
    assert result.change is Change.SOURCE
    assert result.source_changed
    assert not result.pkgver_changed


def test_new_checksums_are_a_source_change():
    result = diff(edit("sha256sums=('SKIP')", "sha256sums=('deadbeef')"))
    assert result.change is Change.SOURCE
    assert result.checksums_changed
    assert not result.source_changed


def test_an_epoch_bump_counts_like_a_version_change():
    assert diff("epoch=1\n" + BASE).pkgver_changed


def test_a_new_source_array_for_another_architecture_is_a_source_change():
    assert diff(BASE + "source_x86_64=('https://example.org/x.tar.gz')\n").source_changed


def test_pkgrel_resets_when_pkgver_moves():
    assert next_pkgrel(parse(BASE), parse(edit("pkgver=1.0.0", "pkgver=1.1.0"))) == "1"


def test_pkgrel_counts_one_more_revision_for_a_config_change():
    assert next_pkgrel(parse(BASE), parse(edit("  make", "  make -j1"))) == "4"


def test_pkgrel_counts_one_more_revision_for_a_source_change_without_new_pkgver():
    assert next_pkgrel(parse(BASE), parse(edit("_commit=abc", "_commit=def"))) == "4"


def test_pkgrel_is_kept_when_nothing_installed_changes():
    assert next_pkgrel(parse(BASE), parse(BASE + "# note\n")) == "3"


def test_pkgrel_ignores_a_hand_edit_of_the_file():
    text = edit("pkgrel=3", "pkgrel=7").replace("  make", "  make -j1")
    assert next_pkgrel(parse(BASE), parse(text)) == "4"


def test_pkgrel_defaults_to_one_when_the_previous_release_had_none():
    old = parse(BASE.replace("pkgrel=3\n", ""))
    assert next_pkgrel(old, parse(edit("  make", "  make -j1"))) == "2"


def test_pkgrel_rejects_a_previous_value_that_is_not_an_integer():
    with pytest.raises(ValueError, match="not an integer"):
        next_pkgrel(parse(edit("pkgrel=3", "pkgrel=1.5")), parse(BASE))
