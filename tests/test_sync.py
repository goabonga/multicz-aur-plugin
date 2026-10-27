# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

from pathlib import Path

import pytest
from multicz.config import Config

from multicz_aur.cli import main
from multicz_aur.sync import SyncError, sync_component

from .conftest import PKGBUILD, SRCINFO, commit, git

CONFIG = Config.model_validate({"components": {"demo": {"paths": ["packages/demo/**"]}}})
FILES = {"packages/demo/PKGBUILD": PKGBUILD, "packages/demo/.SRCINFO": SRCINFO}


@pytest.fixture
def released(repo: Path) -> Path:
    commit(repo, "chore: init", FILES)
    git(repo, "tag", "demo-v0.1.0")
    return repo


def read(repo: Path, name: str) -> str:
    return (repo / "packages/demo" / name).read_text()


def test_a_config_change_costs_one_more_pkgrel(released: Path):
    commit(
        released,
        "build(demo): flags",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("make", "make -j1")},
    )
    result = sync_component(released, CONFIG, "demo")
    assert (result.pkgrel_before, result.pkgrel_after) == ("1", "2")
    assert "pkgrel=2\n" in read(released, "PKGBUILD")
    assert "\tpkgrel = 2\n" in read(released, ".SRCINFO")


def test_a_new_pkgver_resets_pkgrel(released: Path):
    commit(
        released,
        "chore: raise",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("pkgrel=1", "pkgrel=4")},
    )
    git(released, "tag", "demo-v0.2.0")
    commit(
        released, "feat(demo): 2.0", {"packages/demo/PKGBUILD": PKGBUILD.replace("1.0.0", "2.0.0")}
    )
    result = sync_component(released, CONFIG, "demo")
    assert result.pkgrel_after == "1"
    assert "\tpkgver = 2.0.0\n" in read(released, ".SRCINFO")
    assert "\tpkgrel = 1\n" in read(released, ".SRCINFO")


def test_running_twice_changes_nothing_more(released: Path):
    commit(
        released,
        "build(demo): flags",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("make", "make -j1")},
    )
    sync_component(released, CONFIG, "demo")
    again = sync_component(released, CONFIG, "demo")
    assert (again.pkgbuild_changed, again.srcinfo_changed) == (False, False)
    assert again.pkgrel_after == "2"


def test_nothing_installed_changes_nothing(released: Path):
    commit(released, "docs: note", {"packages/demo/PKGBUILD": PKGBUILD + "# note\n"})
    result = sync_component(released, CONFIG, "demo")
    assert result.pkgrel_after == "1"
    assert not result.pkgbuild_changed


def test_dry_run_reports_without_writing(released: Path):
    commit(
        released,
        "build(demo): flags",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("make", "make -j1")},
    )
    before = read(released, "PKGBUILD")
    result = sync_component(released, CONFIG, "demo", write=False)
    assert result.pkgrel_after == "2" and result.pkgbuild_changed
    assert read(released, "PKGBUILD") == before


def test_the_first_release_only_aligns_srcinfo(repo: Path):
    commit(
        repo, "chore: init", {**FILES, "packages/demo/.SRCINFO": SRCINFO.replace("= 1\n", "= 5\n")}
    )
    result = sync_component(repo, CONFIG, "demo")
    assert result.first_release
    assert result.pkgrel_after == "1"
    assert "\tpkgrel = 1\n" in read(repo, ".SRCINFO")


def test_a_package_without_srcinfo_is_fine(repo: Path):
    commit(repo, "chore: init", {"packages/demo/PKGBUILD": PKGBUILD})
    assert sync_component(repo, CONFIG, "demo").srcinfo_changed is False


@pytest.mark.parametrize(
    ("component", "message"),
    [("ghost", "unknown component"), ("other", "no PKGBUILD")],
)
def test_unusable_components_are_reported(repo: Path, component: str, message: str):
    commit(repo, "chore: init", FILES)
    config = Config.model_validate(
        {"components": {"demo": {"paths": ["packages/demo/**"]}, "other": {"paths": ["x/**"]}}}
    )
    with pytest.raises(SyncError, match=message):
        sync_component(repo, config, component)


def test_a_pkgbuild_without_pkgver_is_reported(repo: Path):
    commit(repo, "chore: init", {"packages/demo/PKGBUILD": "pkgname=demo\n"})
    with pytest.raises(SyncError, match="pkgver"):
        sync_component(repo, CONFIG, "demo")


def test_a_pkgbuild_without_pkgrel_is_reported(released: Path):
    text = PKGBUILD.replace("pkgrel=1\n", "").replace("make", "make -j1")
    commit(released, "build(demo): flags", {"packages/demo/PKGBUILD": text})
    with pytest.raises(SyncError, match="pkgrel"):
        sync_component(released, CONFIG, "demo")


def test_a_srcinfo_without_pkgrel_is_reported(repo: Path):
    commit(
        repo, "chore: init", {**FILES, "packages/demo/.SRCINFO": "pkgbase = demo\n\tpkgver = 1\n"}
    )
    with pytest.raises(SyncError, match=r"\.SRCINFO has no pkgrel"):
        sync_component(repo, CONFIG, "demo")


def test_the_command_reports_and_writes(released: Path, monkeypatch, capsys):
    (released / "multicz.toml").write_text('[components.demo]\npaths = ["packages/demo/**"]\n')
    commit(
        released,
        "build(demo): flags",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("make", "make -j1")},
    )
    monkeypatch.chdir(released)
    assert main(["sync", "demo"]) == 0
    assert "pkgrel 1 -> 2" in capsys.readouterr().err
    assert "pkgrel=2\n" in read(released, "PKGBUILD")


def test_the_command_fails_cleanly(released: Path, monkeypatch, capsys):
    monkeypatch.chdir(released)
    assert main(["sync", "demo"]) == 1
    assert "multicz-aur:" in capsys.readouterr().err
