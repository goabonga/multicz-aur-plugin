# Contributing to multicz-aur-plugin

Thanks for taking the time to contribute. This document is the short version
of how to propose a change and what the project expects in return.

## Code of Conduct

Participation in this project is governed by the
[Code of Conduct](CODE_OF_CONDUCT.md). By contributing you agree to abide by
its terms.

## Development setup

```bash
# Clone and sync the project (Python 3.12+).
git clone https://github.com/goabonga/multicz-aur-plugin.git
cd multicz-aur-plugin
uv sync
```

## Running the tests

```bash
uv run pytest
```

The end-to-end tests drive the real `multicz` command on a repository built in
a temporary directory, with the plugin found through its entry point and the
`post_bump` hook running the installed `multicz-aur`. They need `git`.

## Lint and type checks

```bash
uv run ruff check src tests
uv run ruff format --check src tests
```

These checks run in CI and gate the release, along with the tests.

## License headers

Every Python file in the repository must start with the two-line SPDX header
below (after the shebang, if any):

```
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>
```

## Branching and pull requests

1. Fork the repository and create a topic branch from `main`, or from the
   branch of the issue you work on (see [Branch names](#branch-names)).
2. Keep commits small, focused and atomic.
3. Open a pull request against `main`, or against the issue branch for a
   sub-issue.
4. Reviews target correctness, scope and adherence to the
   conventional-commits contract; please do not bundle unrelated changes.

### Branch names

A branch is named after the GitHub issue it addresses:

```
issue-<number>-<slug>
```

`<number>` is the issue number and `<slug>` a few lowercase words separated
by hyphens, for example `issue-12-pkgrel-on-epoch`. Keep it free of `/`: Git
cannot hold `issue-12` and `issue-12/...` at the same time, and the
automation only recognises `issue-*` as a base branch.

| Work | Branch | Created from | Pull request into |
| --- | --- | --- | --- |
| An issue | `issue-<number>-<slug>` | `main` | `main` |
| A sub-issue of an issue | `issue-<number>-<slug>` (its own issue number) | the branch of the parent issue | the branch of the parent issue |

Dependabot branches (`dependabot/...`) are created by Dependabot and need no
naming.

### Merging

Adding the `auto-merge` label to a pull request, by someone with write
access, replays its commits GPG-signed onto its base branch once the
required checks passed, then fast-forwards that branch. The history stays
linear. The commits of a branch pushed unsigned, such as by GitHub's "Update
branch", are re-signed in place.

Dependabot pull requests are rewritten as Conventional Commits and signed.

## Commit messages

Commit messages MUST follow
[Conventional Commits](https://www.conventionalcommits.org/). They drive the
version bumps and changelog computed by
[multicz](https://github.com/goabonga/multicz).

| Type | Effect on version | Use it for |
| --- | --- | --- |
| `feat` | minor | new user-facing capability |
| `fix` | patch | bug fix |
| `perf` | patch | performance improvement |
| `refactor`, `docs`, `test`, `chore`, `ci`, `build`, `style` | none | maintenance, no release |
| `feat!` / `BREAKING CHANGE:` | major | incompatible change |

Examples:

```
feat: report a checksum moved under the same pkgver
fix: keep the quoting of pkgrel when rewriting it
docs: describe the pkgrel rule
```

## Releasing

Releases are fully automated. On every push to `main`, the workflow runs
`multicz bump --commit --tag --push` and then publishes the bumped package to
PyPI. The `chore(release)` commit pushed back by multicz does not start
another run. Maintainers do not need to bump versions, edit changelogs or
create tags by hand.

## Reporting bugs and asking for features

Please open a GitHub issue. For security-sensitive reports, follow
[SECURITY.md](SECURITY.md) instead of the public tracker.
