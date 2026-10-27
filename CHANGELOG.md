# Changelog

All notable changes to this component are documented here.

## [0.1.0] - 2026-10-27

### Added

- read and edit a PKGBUILD without executing it (`5f114e0`)
- keep the versions of a .SRCINFO in step with its PKGBUILD (`cbbe489`)
- classify a PKGBUILD edit and derive the pkgrel it requires (`5ef5b04`)
- find a component's PKGBUILD and the one at its last release (`6d89269`)
- add multicz-aur sync to set pkgrel and align .SRCINFO (`3753a98`)
- add the multicz plugin checking AUR releases (`29d4b3b`)
- add multicz-aur check as a gate that fails on errors (`64c21c9`)
