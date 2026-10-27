# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""The multicz plugin: refuse an AUR release that would ship nothing, or lie.

It runs only where ``[plugins.aur]`` is declared in the root config, on the
components whose directory holds a PKGBUILD, and never executes a PKGBUILD.

``validate`` checks what is wrong at any moment: the ``.SRCINFO`` disagreeing
with the PKGBUILD, a checksum left at ``SKIP`` for a source that is not a VCS
checkout, a component missing the hook that keeps ``pkgrel`` right.

``post_plan`` compares the PKGBUILD with the one at the component's last
release, which is where the commit type and the file content can disagree: an
edit that changes what pacman installs but whose commit type releases nothing.
"""

from __future__ import annotations

from pathlib import Path

from multicz.plugins.protocol import (
    BasePlugin,
    OwnershipContext,
    PluginContext,
    Severity,
    Violation,
)

from . import srcinfo
from .classify import Change, classify, next_pkgrel
from .pkgbuild import Pkgbuild, expand, parse
from .release import PKGBUILD, SRCINFO, aur_components, last_tag, released_pkgbuild

HOOK = "multicz-aur sync"
_VCS = ("git+", "svn+", "hg+", "bzr+", "fossil+")
_SUM_FIELDS = ("md5", "sha1", "sha224", "sha256", "sha384", "sha512", "b2", "cksum")


class AurPlugin(BasePlugin):
    name = "aur"

    def validate(self, ctx: OwnershipContext) -> list[Violation]:
        found: list[Violation] = []
        for component, directory in aur_components(ctx.repo, ctx.config).items():
            found += self._static_checks(ctx, component, directory)
        return found

    def post_plan(self, ctx: PluginContext) -> list[Violation]:
        found: list[Violation] = []
        for component, directory in aur_components(ctx.repo, ctx.config).items():
            released = released_pkgbuild(ctx.repo, ctx.config, component)
            if released is None:
                continue
            current = parse((ctx.repo / directory / PKGBUILD).read_text(encoding="utf-8"))
            found += self._release_checks(ctx, component, directory, released, current)
        return found

    def status_lines(self, ctx: PluginContext) -> list[str]:
        lines = []
        for component, directory in aur_components(ctx.repo, ctx.config).items():
            if component not in ctx.plan.bumps:
                continue
            released = released_pkgbuild(ctx.repo, ctx.config, component)
            if released is None:
                continue
            current = parse((ctx.repo / directory / PKGBUILD).read_text(encoding="utf-8"))
            try:
                target = next_pkgrel(released, current)
            except ValueError:
                continue
            diff = classify(released, current)
            lines.append(f"aur: {component} pkgrel -> {target} ({diff.change.value} change)")
        return lines

    # ------------------------------------------------------------------

    def _static_checks(
        self, ctx: OwnershipContext, component: str, directory: Path
    ) -> list[Violation]:
        found: list[Violation] = []
        pkgbuild_path = directory / PKGBUILD

        def report(severity: Severity, message: str, file: Path = pkgbuild_path) -> None:
            found.append(
                Violation(severity, message, file=file, component=component, plugin=self.name)
            )

        pkgbuild = parse((ctx.repo / pkgbuild_path).read_text(encoding="utf-8"))
        pkgrel = pkgbuild.scalar("pkgrel")
        if pkgrel is not None and not pkgrel.isdecimal():
            report(Severity.error, f"pkgrel {pkgrel!r} is not a positive integer")

        srcinfo_path = directory / SRCINFO
        if (ctx.repo / srcinfo_path).is_file():
            text = (ctx.repo / srcinfo_path).read_text(encoding="utf-8")
            for problem in srcinfo.mismatches(text, pkgbuild):
                report(Severity.error, problem, srcinfo_path)
        else:
            report(Severity.warning, f"no {SRCINFO} next to the PKGBUILD", srcinfo_path)

        for message in _skipped_checksums(pkgbuild):
            report(Severity.error, message)

        if not any(HOOK in command for command in ctx.config.components[component].post_bump):
            report(
                Severity.error,
                f"post_bump does not run `{HOOK} {component}`: pkgrel would not follow the release",
                Path("multicz.toml"),
            )
        elif ctx.config.project.post_bump_policy != "allow":
            report(
                Severity.error,
                f'post_bump_policy is not "allow": `{HOOK}` would be skipped on bump',
                Path("multicz.toml"),
            )
        return found

    def _release_checks(
        self,
        ctx: PluginContext,
        component: str,
        directory: Path,
        released: Pkgbuild,
        current: Pkgbuild,
    ) -> list[Violation]:
        found: list[Violation] = []
        pkgbuild_path = directory / PKGBUILD
        tag = last_tag(ctx.repo, ctx.config, component)
        diff = classify(released, current)
        planned = ctx.plan.bumps.get(component)

        def report(severity: Severity, message: str) -> None:
            found.append(
                Violation(
                    severity, message, file=pkgbuild_path, component=component, plugin=self.name
                )
            )

        reasons = ", ".join(diff.reasons)
        if diff.change is not Change.NONE and planned is None:
            report(
                Severity.error,
                f"the PKGBUILD changed since {tag} ({reasons}) but no commit releases it: "
                "use feat, fix or build, whose commits make a release",
            )
        if diff.change is Change.NONE and planned is not None:
            report(
                Severity.warning,
                f"released with no change to what pacman installs since {tag}: "
                "the AUR would receive nothing new",
            )
        if diff.checksums_changed and not diff.source_changed and not diff.pkgver_changed:
            report(
                Severity.warning,
                "the checksums changed but neither pkgver nor the source did: "
                "the upstream content moved under the same name",
            )
        if diff.change is Change.SOURCE and planned is not None and planned.kind == "patch":
            report(
                Severity.info,
                f"new upstream content ({reasons}) is released as a patch; "
                "feat is the usual type for it",
            )
        try:
            expected = next_pkgrel(released, current)
        except ValueError as exc:
            report(Severity.error, str(exc))
        else:
            actual = current.scalar("pkgrel")
            if actual is not None and actual != expected and diff.change is not Change.NONE:
                report(
                    Severity.info,
                    f"pkgrel is {actual} in the file; `{HOOK}` will set {expected} on release",
                )
        return found


def _skipped_checksums(pkgbuild: Pkgbuild) -> list[str]:
    """Checksums left at ``SKIP`` for a source that is not a VCS checkout."""
    scalars = pkgbuild.scalars
    sources = [expand(s, scalars) for s in pkgbuild.array("source")]
    problems = []
    for field in _SUM_FIELDS:
        sums = pkgbuild.array(f"{field}sums")
        if len(sums) != len(sources):
            continue
        for source, checksum in zip(sources, sums, strict=True):
            target = source.partition("::")[2] or source
            if checksum == "SKIP" and not target.startswith(_VCS):
                problems.append(f"{field}sums is SKIP for {source!r}, which is not a VCS source")
    return problems
