# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""The plugin and the hook through the real multicz CLI, on a repo shaped like aur-packages.

multicz finds the plugin through its entry point, and the ``post_bump`` hook
runs the installed ``multicz-aur`` command, exactly as in a release.
"""

import os
import sys
from pathlib import Path

import pytest
from multicz.cli import app
from typer.testing import CliRunner

from multicz_aur.cli import main as aur_main

from .conftest import commit, git

runner = CliRunner()

ROOT = """\
[project]
tag_format = "{component}-v{version}"
initial_version = "0.1.0"
post_bump_policy = "allow"

[project.bump_rules]
feat = "minor"
fix = "patch"
build = "patch"

[plugins.aur]

[[component.path]]
path = "packages/*"
"""

# multicz owns pkgver: it writes it into the PKGBUILD and the .SRCINFO.
OWNED_COMPONENT = """\
[components.owned]
changelog = "CHANGELOG.md"
bump_files = [
    { file = "PKGBUILD", key = 'regex:^pkgver=([^\\s#]+)' },
    { file = ".SRCINFO", key = 'regex:^\\tpkgver = (\\S+)' },
]
post_bump = ["multicz-aur sync owned"]
"""

# pkgver follows upstream: multicz never writes it.
WRAPPER_COMPONENT = """\
[components.wrapper]
changelog = "CHANGELOG.md"
post_bump = ["multicz-aur sync wrapper"]
"""


NO_HOOK = '[components.wrapper]\nchangelog = "CHANGELOG.md"\n'


def pkgbuild(
    name: str, pkgver: str, pkgrel: int = 1, sums: str = "aaaa", build: str = "make"
) -> str:
    return f"""\
pkgname={name}
pkgver={pkgver}
pkgrel={pkgrel}
depends=('glibc')
source=("https://example.org/{name}-$pkgver.tar.gz")
sha256sums=('{sums}')

build() {{
  {build}
}}
"""


def srcinfo(name: str, pkgver: str, pkgrel: int = 1, sums: str = "aaaa") -> str:
    return (
        f"pkgbase = {name}\n\tpkgver = {pkgver}\n\tpkgrel = {pkgrel}\n\tdepends = glibc\n"
        f"\tsource = https://example.org/{name}-{pkgver}.tar.gz\n\tsha256sums = {sums}\n\n"
        f"pkgname = {name}\n"
    )


def files(name: str, component: str, pkgver: str) -> dict[str, str]:
    return {
        f"packages/{name}/PKGBUILD": pkgbuild(name, pkgver),
        f"packages/{name}/.SRCINFO": srcinfo(name, pkgver),
        f"packages/{name}/multicz.component.toml": component,
    }


@pytest.fixture(autouse=True)
def installed_command_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The hook runs `multicz-aur`: put the one installed next to this interpreter first."""
    bin_dir = str(Path(sys.executable).parent)
    monkeypatch.setenv("PATH", bin_dir + os.pathsep + os.environ["PATH"])


@pytest.fixture
def project(repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    commit(
        repo,
        "chore: init",
        {
            "multicz.toml": ROOT,
            **files("owned", OWNED_COMPONENT, "1.0.0"),
            **files("wrapper", WRAPPER_COMPONENT, "6.1.1"),
        },
    )
    # The packages have been released once, so there is a baseline to compare with.
    git(repo, "tag", "owned-v0.1.0")
    git(repo, "tag", "wrapper-v0.1.0")
    monkeypatch.chdir(repo)
    return repo


def check_main() -> int:
    return aur_main(["check"])


def text(repo: Path, package: str, name: str) -> str:
    return (repo / "packages" / package / name).read_text()


def run(*args: str):
    return runner.invoke(app, list(args))


def test_the_plugin_is_discovered_and_a_clean_project_validates(project: Path):
    result = run("validate", "--strict")
    assert result.exit_code == 0, result.output


def test_a_package_owning_its_content_gets_pkgver_and_resets_pkgrel(project: Path):
    commit(project, "feat(owned): add a feature", {"packages/owned/new.txt": "x\n"})
    result = run("bump", "--commit", "--tag")
    assert result.exit_code == 0, result.output
    assert "pkgver=0.2.0\n" in text(project, "owned", "PKGBUILD")
    assert "pkgrel=1\n" in text(project, "owned", "PKGBUILD")
    assert "\tpkgver = 0.2.0\n" in text(project, "owned", ".SRCINFO")
    assert "owned-v0.2.0" in git(project, "tag", "--list")


def test_the_release_commit_carries_the_files_the_hook_touched(project: Path):
    commit(
        project,
        "build(wrapper): flags",
        {"packages/wrapper/PKGBUILD": pkgbuild("wrapper", "6.1.1", build="make -j1")},
    )
    assert run("bump", "--commit", "--tag").exit_code == 0
    changed = git(project, "show", "--name-only", "--format=", "HEAD").split()
    assert "packages/wrapper/PKGBUILD" in changed
    assert "packages/wrapper/.SRCINFO" in changed
    assert git(project, "status", "--porcelain") == ""


def test_a_config_change_on_an_upstream_package_costs_one_pkgrel(project: Path):
    commit(
        project,
        "build(wrapper): flags",
        {"packages/wrapper/PKGBUILD": pkgbuild("wrapper", "6.1.1", build="make -j1")},
    )
    result = run("bump", "--commit", "--tag")
    assert result.exit_code == 0, result.output
    assert "pkgver=6.1.1\n" in text(project, "wrapper", "PKGBUILD")
    assert "pkgrel=2\n" in text(project, "wrapper", "PKGBUILD")
    assert "\tpkgrel = 2\n" in text(project, "wrapper", ".SRCINFO")
    assert "wrapper-v0.1.1" in git(project, "tag", "--list")


def test_pkgrel_keeps_counting_across_releases_then_resets_on_a_new_source(project: Path):
    commit(
        project,
        "build(wrapper): flags",
        {"packages/wrapper/PKGBUILD": pkgbuild("wrapper", "6.1.1", build="make -j1")},
    )
    assert run("bump", "--commit", "--tag").exit_code == 0
    commit(
        project,
        "fix(wrapper): more flags",
        {"packages/wrapper/PKGBUILD": pkgbuild("wrapper", "6.1.1", pkgrel=2, build="make -j2")},
    )
    assert run("bump", "--commit", "--tag").exit_code == 0
    assert "pkgrel=3\n" in text(project, "wrapper", "PKGBUILD")

    commit(
        project,
        "feat(wrapper): update to 7.0.0",
        {
            "packages/wrapper/PKGBUILD": pkgbuild(
                "wrapper", "7.0.0", pkgrel=3, sums="bbbb", build="make -j2"
            ),
            "packages/wrapper/.SRCINFO": srcinfo("wrapper", "7.0.0", pkgrel=3, sums="bbbb"),
        },
    )
    assert run("bump", "--commit", "--tag").exit_code == 0
    assert "pkgver=7.0.0\n" in text(project, "wrapper", "PKGBUILD")
    assert "pkgrel=1\n" in text(project, "wrapper", "PKGBUILD")
    assert "\tpkgrel = 1\n" in text(project, "wrapper", ".SRCINFO")


def test_a_hand_edited_pkgrel_is_overridden_by_the_rule(project: Path):
    commit(
        project,
        "build(wrapper): flags",
        {"packages/wrapper/PKGBUILD": pkgbuild("wrapper", "6.1.1", pkgrel=9, build="make -j1")},
    )
    assert run("bump", "--commit", "--tag").exit_code == 0
    assert "pkgrel=2\n" in text(project, "wrapper", "PKGBUILD")


def test_a_config_edit_typed_chore_is_shown_by_plan_and_refused_by_check(project: Path):
    commit(
        project,
        "chore(wrapper): flags",
        {"packages/wrapper/PKGBUILD": pkgbuild("wrapper", "6.1.1", build="make -j1")},
    )
    assert "no commit releases it" in run("plan").output
    assert check_main() == 1


def test_that_edit_releases_nothing_when_bumped(project: Path):
    """multicz itself stops before the plugins when no commit releases: no tag, no write."""
    commit(
        project,
        "chore(wrapper): flags",
        {"packages/wrapper/PKGBUILD": pkgbuild("wrapper", "6.1.1", build="make -j1")},
    )
    run("bump", "--commit", "--tag")
    assert "wrapper-v0.1.1" not in git(project, "tag", "--list")
    assert "pkgrel=1\n" in text(project, "wrapper", "PKGBUILD")


def test_check_passes_on_a_sound_project_and_after_a_proper_edit(project: Path):
    assert check_main() == 0
    commit(
        project,
        "build(wrapper): flags",
        {"packages/wrapper/PKGBUILD": pkgbuild("wrapper", "6.1.1", build="make -j1")},
    )
    assert check_main() == 0


def test_the_plan_shows_the_pkgrel_a_release_will_carry(project: Path):
    commit(
        project,
        "build(wrapper): flags",
        {"packages/wrapper/PKGBUILD": pkgbuild("wrapper", "6.1.1", build="make -j1")},
    )
    assert "aur: wrapper pkgrel -> 2 (config change)" in run("plan").output


def test_a_package_that_forgot_the_hook_fails_validation(project: Path):
    commit(
        project,
        "chore: drop the hook",
        {"packages/wrapper/multicz.component.toml": NO_HOOK},
    )
    result = run("validate", "--strict")
    assert result.exit_code != 0
    assert "multicz-aur sync wrapper" in result.output


def test_a_stale_srcinfo_fails_validation(project: Path):
    commit(
        project,
        "fix(wrapper): version",
        {"packages/wrapper/PKGBUILD": pkgbuild("wrapper", "6.2.0")},
    )
    result = run("validate", "--strict")
    assert result.exit_code != 0
    assert ".SRCINFO" in result.output


def test_a_skipped_checksum_on_a_tarball_fails_validation(project: Path):
    commit(
        project,
        "fix(wrapper): sums",
        {"packages/wrapper/PKGBUILD": pkgbuild("wrapper", "6.1.1", sums="SKIP")},
    )
    result = run("validate", "--strict")
    assert result.exit_code != 0
    assert "SKIP" in result.output
