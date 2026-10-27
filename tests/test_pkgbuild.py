# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

import pytest

from multicz_aur.pkgbuild import expand, parse, set_scalar

SAMPLE = """\
# Maintainer: Chris <goabonga@pm.me>
pkgname=demo
pkgver=1.2.3  # upstream
pkgrel=2
_commit='abc123'
pkgdesc="A demo: with 'quotes' and a # hash"
arch=('x86_64' 'aarch64')
depends=(
  'glibc'   # the C library
  "zlib"
  openssl
)
source=("${pkgname}::git+https://example.org/demo.git#commit=${_commit}"
        'local.patch')
sha256sums=('SKIP'
            'deadbeef')

pkgver() {
  cd "$srcdir/$pkgname"
  pkgver=9.9.9
  printf '%s' "${pkgver}"
}

build() {
  if [ -n "$x" ]; then
    echo "}"
  fi
}

package() {
  pkgrel=77
  install -Dm755 demo "$pkgdir/usr/bin/demo"
}
"""


def test_scalars_keep_their_unquoted_value():
    p = parse(SAMPLE)
    assert p.scalar("pkgname") == "demo"
    assert p.scalar("pkgver") == "1.2.3"
    assert p.scalar("pkgrel") == "2"
    assert p.scalar("_commit") == "abc123"


def test_quotes_and_hashes_inside_a_quoted_value_are_kept():
    assert parse(SAMPLE).scalar("pkgdesc") == "A demo: with 'quotes' and a # hash"


def test_arrays_handle_quotes_comments_and_multiple_lines():
    p = parse(SAMPLE)
    assert p.array("arch") == ["x86_64", "aarch64"]
    assert p.array("depends") == ["glibc", "zlib", "openssl"]
    assert p.array("sha256sums") == ["SKIP", "deadbeef"]
    assert p.array("source") == [
        "${pkgname}::git+https://example.org/demo.git#commit=${_commit}",
        "local.patch",
    ]


def test_assignments_inside_functions_are_ignored():
    p = parse(SAMPLE)
    assert p.scalar("pkgver") == "1.2.3"
    assert p.scalar("pkgrel") == "2"


def test_a_brace_inside_a_string_does_not_end_a_function():
    p = parse(SAMPLE + "pkgepoch=1\n")
    assert p.scalar("pkgepoch") == "1"


def test_missing_names_are_absent():
    p = parse(SAMPLE)
    assert p.scalar("epoch") is None
    assert p.array("makedepends") == []


def test_first_assignment_wins():
    assert parse("pkgrel=1\npkgrel=2\n").scalar("pkgrel") == "1"


def test_a_scalar_read_as_an_array_is_a_one_element_list():
    assert parse("pkgname=demo\n").array("pkgname") == ["demo"]


def test_unbalanced_array_is_skipped_not_guessed():
    assert parse("source=('a'\n").array("source") == []


def test_line_numbers_are_one_based():
    assert parse(SAMPLE).assignments["pkgrel"].line == 4


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("pkgrel=2\n", "pkgrel=9\n"),
        ("pkgrel='2'\n", "pkgrel='9'\n"),
        ('pkgrel="2"\n', 'pkgrel="9"\n'),
        ("pkgrel=2 # note\n", "pkgrel=9 # note\n"),
    ],
)
def test_set_scalar_keeps_quoting_and_what_follows(line: str, expected: str):
    assert set_scalar("a=1\n" + line + "b=2\n", "pkgrel", "9") == "a=1\n" + expected + "b=2\n"


def test_set_scalar_only_touches_the_top_level_assignment():
    out = set_scalar(SAMPLE, "pkgrel", "3")
    assert "pkgrel=3\n" in out
    assert "  pkgrel=77\n" in out
    assert out.replace("pkgrel=3", "pkgrel=2") == SAMPLE


def test_set_scalar_rejects_unknown_names_and_arrays():
    with pytest.raises(KeyError):
        set_scalar(SAMPLE, "epoch", "1")
    with pytest.raises(KeyError):
        set_scalar(SAMPLE, "depends", "x")


def test_expand_substitutes_known_scalars_only():
    scalars = parse(SAMPLE).scalars
    assert expand("${pkgname}-$pkgver.tar", scalars) == "demo-1.2.3.tar"
    assert expand("${unknown}/${_commit}", scalars) == "${unknown}/abc123"


@pytest.mark.parametrize(
    "text",
    ["x=(a\\)\n", "x=a\\"],
    ids=["array", "scalar"],
)
def test_a_dangling_escape_is_skipped_not_guessed(text: str):
    assert parse(text).assignments == {}


def test_an_empty_value_at_the_end_of_the_file_is_an_empty_string():
    assert parse("x=").scalar("x") == ""


def test_escaped_quotes_stay_inside_a_double_quoted_scalar():
    assert parse('pkgdesc="say \\"hi\\""\n').scalar("pkgdesc") == 'say "hi"'


def test_a_word_glued_to_its_closing_quote_is_not_treated_as_quoted():
    found = parse('x="a"b\n').assignments["x"]
    assert found.quote == ""


def test_escaped_quotes_and_nested_parentheses_do_not_end_an_array():
    assert parse('x=("a\\"b" (c) d)\n').array("x") == ['a"b', "(c)", "d"]


def test_functions_with_quotes_comments_and_nested_braces_are_skipped_whole():
    text = (
        "build() {\n"
        '  echo \'a } b\' "c \\" } d"  # } still a comment\n'
        "  if true; then { :; } fi\n"
        "}\n"
        "pkgrel=3\n"
    )
    assert parse(text).scalar("pkgrel") == "3"


def test_an_unterminated_function_swallows_the_rest_of_the_file():
    assert parse("build() {\n  make\npkgrel=3\n").assignments == {}
