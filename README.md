<h1 align="center">
  <img src="https://github.com/goabonga/multicz/raw/main/docs/multicz.svg" alt="multicz" width="120" /><br/>
  multicz-aur-plugin
</h1>

<p align="center">
  <em>A multicz plugin that keeps AUR packages honest.</em>
</p>

<p align="center">
  <a href="https://github.com/goabonga/multicz-aur-plugin/actions/workflows/ci.yml"><img src="https://github.com/goabonga/multicz-aur-plugin/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"/></a>
  <a href="https://codecov.io/gh/goabonga/multicz-aur-plugin"><img src="https://img.shields.io/codecov/c/github/goabonga/multicz-aur-plugin?logo=codecov" alt="Codecov"/></a>
  <a href="https://pypi.org/project/multicz-aur-plugin/"><img src="https://img.shields.io/pypi/v/multicz-aur-plugin.svg" alt="PyPI"/></a>
  <a href="https://github.com/goabonga/multicz-aur-plugin/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"/></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python"/></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv"/></a>
</p>

**multicz-aur-plugin** adds what [multicz](https://github.com/goabonga/multicz)
cannot own for an AUR package: `pkgrel`, the positive integer that counts
packaging revisions of one `pkgver`. It applies the rule on each release,
keeps `.SRCINFO` in step with the PKGBUILD, and refuses the releases that
would ship nothing or lie about what they ship. A PKGBUILD is only ever read
as text, never sourced.

## Requirements

- Python 3.12+
- `git`
- [multicz](https://github.com/goabonga/multicz) 1.9+

## Installation

The plugin is discovered through multicz's entry points, so it has to live in
the same environment as multicz:

```bash
pip install multicz-aur-plugin
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install multicz --with multicz-aur-plugin
```

## Usage

In the root `multicz.toml`, opt in and allow the `post_bump` hook:

```toml
[project]
post_bump_policy = "allow"

[plugins.aur]
```

In each package's component, run the sync after multicz writes its files:

```toml
[components.example-pkg]
post_bump = ["multicz-aur sync example-pkg"]
```

A component is an AUR package when a `PKGBUILD` sits in the directory of its
`paths`. Others are ignored.

```bash
multicz-aur sync <component> [--dry-run]   # set pkgrel, align .SRCINFO
multicz-aur check                          # exit 1 on any error
```

### The `pkgrel` rule

On each release, compared with the PKGBUILD at the component's last tag:

| What changed | `pkgrel` |
| --- | --- |
| `pkgver` (or `epoch`) | `1` |
| the source or the checksums, with the same `pkgver` | previous + 1 |
| the configuration only (`depends`, build flags, install paths) | previous + 1 |
| nothing pacman installs (comments, spacing) | unchanged |

It is computed from the last release, not from the edited file, so a
hand-edited `pkgrel` is overridden and running the command twice changes
nothing more.

### What it checks

`multicz validate` reports, for every package:

- `.SRCINFO` disagreeing with the PKGBUILD on `pkgver` or `pkgrel`;
- a checksum left at `SKIP` for a source that is not a VCS checkout;
- a `pkgrel` that is not an integer;
- a component missing the `post_bump` hook, or a `post_bump_policy` that would
  skip it.

`multicz plan` and `multicz bump` also compare the PKGBUILD with the last
release and report an edit that changes the package but whose commit type
releases nothing (`chore`, `docs`, `refactor`), checksums that moved under the
same `pkgver`, and a release that changes nothing pacman installs.

multicz prints those findings in `plan` without failing, and `bump` stops
before the plugins when no commit releases, which is the `chore` case. To fail
a pull request on them, run `multicz-aur check`.

## Development

```bash
git clone https://github.com/goabonga/multicz-aur-plugin.git
cd multicz-aur-plugin
uv sync

# Quality gates (mirrored in CI).
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pyright
uv run pytest --cov

# Install the pre-commit + commit-msg hooks.
uv run pre-commit install
```

The unit tests cover the PKGBUILD reader, the classification and the rule. The
end-to-end tests build a repository shaped like a collection of AUR packages
and drive the real `multicz` command, with the plugin found through its entry
point and the hook running the installed `multicz-aur`.

## Versioning and release

multicz-aur-plugin is versioned by multicz itself. Every push to `main` runs
`multicz bump --commit --tag --push` - driven by
[Conventional Commits](https://www.conventionalcommits.org/) - then publishes
to PyPI.

```bash
# Preview the next release against the current branch.
uv run multicz plan
```

## Contributing

See [CONTRIBUTING.md](https://github.com/goabonga/multicz-aur-plugin/blob/main/CONTRIBUTING.md)
for the workflow, the branch and commit-message conventions, and the
test/lint expectations. By participating you agree to the
[Code of Conduct](https://github.com/goabonga/multicz-aur-plugin/blob/main/CODE_OF_CONDUCT.md).

Security issues: please follow the disclosure process in
[SECURITY.md](https://github.com/goabonga/multicz-aur-plugin/blob/main/SECURITY.md).

## License

Distributed under the
[MIT License](https://github.com/goabonga/multicz-aur-plugin/blob/main/LICENSE).
