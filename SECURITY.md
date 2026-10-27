# Security Policy

## Supported versions

Security fixes are applied only to the latest released minor of
`multicz-aur-plugin`.

| Version | Supported |
| --- | --- |
| latest minor on PyPI | ✅ |
| Older minors or pre-releases | ❌ |

## Reporting a vulnerability

**Please do not open a public issue.** GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
is the preferred channel:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Fill in the form with the affected version, reproduction steps and
   suggested mitigation.

If you cannot use GitHub's form, email **goabonga@pm.me** with the same
information. PGP encryption is available on request.

You can expect:

- an acknowledgement within **3 business days**;
- a triage assessment (severity, scope, affected versions) within **10
  business days**;
- a fix or written mitigation plan before any public disclosure.

## Scope

The plugin reads PKGBUILD and `.SRCINFO` files that come from pull requests,
and runs in CI next to secrets. It treats them as text: a PKGBUILD is never
sourced or executed, and a report showing otherwise, or showing a crafted file
that makes the parser misbehave, is in scope. So is anything that makes
`multicz-aur sync` write outside the package directory. Vulnerabilities in
multicz itself or in a package's upstream should be reported there.

## Disclosure process

Coordinated disclosure is the default. Once a fix is released:

1. A patched version is published to PyPI.
2. A GitHub Security Advisory is opened with a CVE when applicable.
3. The reporter is credited in the advisory unless they request anonymity.

Thanks for helping keep `multicz-aur-plugin` and its users safe.
