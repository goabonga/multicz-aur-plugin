# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

from pathlib import Path

import pytest
from multicz.config import Config
from multicz.planner import build_plan
from multicz.plugins.protocol import OwnershipContext, PluginContext, Severity

from multicz_aur.plugin import AurPlugin

from .conftest import PKGBUILD, SRCINFO, commit, git

HOOKED = {
    "paths": ["packages/demo/**"],
    "post_bump": ["multicz-aur sync demo"],
}


def make_config(**project) -> Config:
    return Config.model_validate(
        {
            "project": {
                "post_bump_policy": "allow",
                "bump_rules": {"build": "patch"},
                **project,
            },
            "components": {"demo": HOOKED, "tool": {"paths": ["tools/**"]}},
        }
    )


FILES = {
    "packages/demo/PKGBUILD": PKGBUILD,
    "packages/demo/.SRCINFO": SRCINFO,
    "tools/run.sh": "x\n",
}


def validate(repo: Path, config: Config | None = None):
    ctx = OwnershipContext(config=config or make_config(), repo=repo, plugin_config={})
    return AurPlugin().validate(ctx)


def post_plan(repo: Path, config: Config | None = None):
    config = config or make_config()
    plan = build_plan(repo, config)
    ctx = PluginContext(config=config, repo=repo, plan=plan, plugin_config={})
    return AurPlugin().post_plan(ctx), plan


def messages(violations, severity: Severity) -> list[str]:
    return [v.message for v in violations if v.severity is severity]


@pytest.fixture
def released(repo: Path) -> Path:
    commit(repo, "chore: init", FILES)
    git(repo, "tag", "demo-v0.1.0")
    git(repo, "tag", "tool-v0.1.0")
    return repo


# --- validate -------------------------------------------------------------


def test_a_consistent_package_has_nothing_to_report(repo: Path):
    commit(repo, "chore: init", FILES)
    assert validate(repo) == []


def test_non_aur_components_are_left_alone(repo: Path):
    commit(repo, "chore: init", {"tools/run.sh": "x\n"})
    assert validate(repo) == []


def test_a_component_without_the_hook_is_an_error(repo: Path):
    commit(repo, "chore: init", FILES)
    config = Config.model_validate(
        {
            "project": {"post_bump_policy": "allow"},
            "components": {"demo": {"paths": ["packages/demo/**"]}},
        }
    )
    assert any(
        "does not run `multicz-aur sync demo`" in m
        for m in messages(validate(repo, config), Severity.error)
    )


def test_hooks_that_the_policy_would_skip_are_an_error(repo: Path):
    commit(repo, "chore: init", FILES)
    config = make_config(post_bump_policy="deny")
    assert any("post_bump_policy" in m for m in messages(validate(repo, config), Severity.error))


def test_srcinfo_disagreeing_with_the_pkgbuild_is_an_error(repo: Path):
    commit(
        repo, "chore: init", {**FILES, "packages/demo/.SRCINFO": SRCINFO.replace("1.0.0", "0.9")}
    )
    errors = messages(validate(repo), Severity.error)
    assert any("pkgver is '0.9' in .SRCINFO" in m for m in errors)


def test_a_missing_srcinfo_is_a_warning(repo: Path):
    commit(repo, "chore: init", {"packages/demo/PKGBUILD": PKGBUILD})
    assert messages(validate(repo), Severity.warning) == ["no .SRCINFO next to the PKGBUILD"]


def test_a_non_integer_pkgrel_is_an_error(repo: Path):
    commit(
        repo,
        "chore: init",
        {**FILES, "packages/demo/PKGBUILD": PKGBUILD.replace("pkgrel=1", "pkgrel=1.5")},
    )
    assert any("not a positive integer" in m for m in messages(validate(repo), Severity.error))


def test_skip_is_an_error_for_a_tarball(repo: Path):
    text = PKGBUILD.replace("'aaaa'", "'SKIP'")
    commit(repo, "chore: init", {**FILES, "packages/demo/PKGBUILD": text})
    assert any("sha256sums is SKIP" in m for m in messages(validate(repo), Severity.error))


@pytest.mark.parametrize(
    "source",
    ['"git+https://example.org/demo.git"', '"demo::git+https://example.org/demo.git#commit=abc"'],
)
def test_skip_is_fine_for_a_vcs_source(repo: Path, source: str):
    text = PKGBUILD.replace('"https://example.org/demo-$pkgver.tar.gz"', source).replace(
        "'aaaa'", "'SKIP'"
    )
    commit(repo, "chore: init", {**FILES, "packages/demo/PKGBUILD": text})
    assert messages(validate(repo), Severity.error) == []


# --- post_plan ------------------------------------------------------------


def test_the_first_release_has_no_baseline_to_compare(repo: Path):
    commit(repo, "chore: init", FILES)
    commit(
        repo, "feat(demo): more", {"packages/demo/PKGBUILD": PKGBUILD.replace("make", "make -j1")}
    )
    assert post_plan(repo)[0] == []


def test_an_edit_whose_commit_type_releases_nothing_is_an_error(released: Path):
    commit(
        released,
        "chore(demo): flags",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("make", "make -j1")},
    )
    violations, plan = post_plan(released)
    assert "demo" not in plan.bumps
    assert any("no commit releases it" in m for m in messages(violations, Severity.error))


def test_a_source_bump_typed_chore_is_the_same_error(released: Path):
    commit(
        released,
        "chore(demo): update",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("1.0.0", "1.1.0")},
    )
    errors = messages(post_plan(released)[0], Severity.error)
    assert any("pkgver 1.0.0 -> 1.1.0" in m for m in errors)


def test_a_config_edit_typed_build_is_accepted(released: Path):
    commit(
        released,
        "build(demo): flags",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("make", "make -j1")},
    )
    violations, plan = post_plan(released)
    assert "demo" in plan.bumps
    assert messages(violations, Severity.error) == []


def test_a_release_that_changes_nothing_installed_is_a_warning(released: Path):
    commit(released, "feat(demo): note", {"packages/demo/README.md": "hello\n"})
    violations, plan = post_plan(released)
    assert "demo" in plan.bumps
    assert any("nothing new" in m for m in messages(violations, Severity.warning))


def test_checksums_moving_under_the_same_name_is_a_warning(released: Path):
    commit(
        released,
        "fix(demo): sums",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("'aaaa'", "'bbbb'")},
    )
    warnings = messages(post_plan(released)[0], Severity.warning)
    assert any("upstream content moved" in m for m in warnings)


def test_new_upstream_content_released_as_a_patch_is_advised(released: Path):
    commit(
        released,
        "fix(demo): update",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("1.0.0", "1.0.1")},
    )
    infos = messages(post_plan(released)[0], Severity.info)
    assert any("feat is the usual type" in m for m in infos)


def test_a_feat_for_new_upstream_content_is_not_advised_against(released: Path):
    commit(
        released,
        "feat(demo): update",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("1.0.0", "1.1.0")},
    )
    assert not any("usual type" in m for m in messages(post_plan(released)[0], Severity.info))


def test_a_hand_edited_pkgrel_is_reported_as_overridden(released: Path):
    text = PKGBUILD.replace("pkgrel=1", "pkgrel=7").replace("make", "make -j1")
    commit(released, "build(demo): flags", {"packages/demo/PKGBUILD": text})
    infos = messages(post_plan(released)[0], Severity.info)
    assert any("pkgrel is 7 in the file; `multicz-aur sync` will set 2" in m for m in infos)


def test_unreleased_non_aur_components_are_ignored(released: Path):
    commit(released, "feat(tool): more", {"tools/run.sh": "y\n"})
    assert post_plan(released)[0] == []


def test_status_lines_show_the_pkgrel_a_release_will_carry(released: Path):
    commit(
        released,
        "build(demo): flags",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("make", "make -j1")},
    )
    config = make_config()
    plan = build_plan(released, config)
    ctx = PluginContext(config=config, repo=released, plan=plan, plugin_config={})
    assert AurPlugin().status_lines(ctx) == ["aur: demo pkgrel -> 2 (config change)"]


def test_every_finding_names_the_plugin(released: Path):
    commit(
        released,
        "chore(demo): flags",
        {"packages/demo/PKGBUILD": PKGBUILD.replace("make", "make -j1")},
    )
    commit(
        released,
        "chore: skip",
        {
            "packages/demo/PKGBUILD": PKGBUILD.replace("make", "make -j1").replace(
                "'aaaa'", "'SKIP'"
            )
        },
    )
    findings = post_plan(released)[0] + validate(released)
    assert findings
    assert {v.plugin for v in findings} == {"aur"}


def test_status_lines_skip_a_package_never_released(repo: Path):
    commit(repo, "chore: init", FILES)
    commit(repo, "feat(demo): first", {"packages/demo/new.txt": "x\n"})
    config = make_config()
    plan = build_plan(repo, config)
    assert "demo" in plan.bumps
    ctx = PluginContext(config=config, repo=repo, plan=plan, plugin_config={})
    assert AurPlugin().status_lines(ctx) == []


def test_a_previous_pkgrel_that_is_not_an_integer_is_reported_everywhere(repo: Path):
    commit(
        repo,
        "chore: init",
        {**FILES, "packages/demo/PKGBUILD": PKGBUILD.replace("pkgrel=1", "pkgrel=1.5")},
    )
    git(repo, "tag", "demo-v0.1.0")
    commit(
        repo, "build(demo): flags", {"packages/demo/PKGBUILD": PKGBUILD.replace("make", "make -j1")}
    )
    config = make_config()
    plan = build_plan(repo, config)
    ctx = PluginContext(config=config, repo=repo, plan=plan, plugin_config={})
    assert any("not an integer" in m for m in messages(AurPlugin().post_plan(ctx), Severity.error))
    assert AurPlugin().status_lines(ctx) == []
