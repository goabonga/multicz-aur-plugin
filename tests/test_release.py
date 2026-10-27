# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

from pathlib import Path

from multicz.config import Config

from multicz_aur.release import aur_components, last_tag, package_dir, read_at, released_pkgbuild

from .conftest import PKGBUILD, commit, git

CONFIG = Config.model_validate(
    {
        "components": {
            "demo": {"paths": ["packages/demo/**"]},
            "tool": {"paths": ["tools/**"]},
            "broad": {"paths": ["**"]},
        }
    }
)


def test_package_dir_is_the_directory_holding_the_pkgbuild(repo: Path):
    commit(repo, "chore: init", {"packages/demo/PKGBUILD": PKGBUILD, "tools/run.sh": "x"})
    assert package_dir(repo, CONFIG, "demo") == Path("packages/demo")


def test_a_component_without_a_pkgbuild_is_not_a_package(repo: Path):
    commit(repo, "chore: init", {"packages/demo/PKGBUILD": PKGBUILD, "tools/run.sh": "x"})
    assert package_dir(repo, CONFIG, "tool") is None
    assert package_dir(repo, CONFIG, "broad") is None


def test_aur_components_lists_only_packages(repo: Path):
    commit(repo, "chore: init", {"packages/demo/PKGBUILD": PKGBUILD, "tools/run.sh": "x"})
    assert aur_components(repo, CONFIG) == {"demo": Path("packages/demo")}


def test_last_tag_follows_the_components_tag_format(repo: Path):
    commit(repo, "chore: init", {"packages/demo/PKGBUILD": PKGBUILD})
    assert last_tag(repo, CONFIG, "demo") is None
    git(repo, "tag", "demo-v0.1.0")
    git(repo, "tag", "demo-v0.2.0")
    git(repo, "tag", "tool-v9.0.0")
    assert last_tag(repo, CONFIG, "demo") == "demo-v0.2.0"


def test_read_at_returns_the_file_as_it_was(repo: Path):
    commit(repo, "chore: init", {"packages/demo/PKGBUILD": PKGBUILD})
    git(repo, "tag", "demo-v0.1.0")
    commit(repo, "fix: edit", {"packages/demo/PKGBUILD": PKGBUILD + "# later\n"})
    assert read_at(repo, "demo-v0.1.0", Path("packages/demo/PKGBUILD")) == PKGBUILD
    assert read_at(repo, "demo-v0.1.0", Path("packages/demo/missing")) is None


def test_released_pkgbuild_is_the_one_at_the_last_tag(repo: Path):
    commit(repo, "chore: init", {"packages/demo/PKGBUILD": PKGBUILD})
    git(repo, "tag", "demo-v0.1.0")
    commit(repo, "fix: edit", {"packages/demo/PKGBUILD": PKGBUILD.replace("1.0.0", "2.0.0")})
    released = released_pkgbuild(repo, CONFIG, "demo")
    assert released is not None
    assert released.scalar("pkgver") == "1.0.0"


def test_there_is_no_released_pkgbuild_before_the_first_tag(repo: Path):
    commit(repo, "chore: init", {"packages/demo/PKGBUILD": PKGBUILD})
    assert released_pkgbuild(repo, CONFIG, "demo") is None
