# Security policy

## Publication boundary

Before publication, review current files and the complete reachable Git history
for credentials, private files and unintended personal information. Include image
metadata and separately review hosted content such as release assets and CI logs;
a repository scan does not cover those automatically. Recheck new content rather
than treating an earlier scan as a continuing security guarantee.

Björn Rudner authorizes publication of his name and existing personal commit
email. Authorization for the five complete recordings, including GPS and metadata,
is maintained in the [recording catalog](docs/development/RECORDINGS.md).
These permissions do not authorize additional private data or change third-party
rights. Repository publication requires separate explicit owner authorization.

## Supported versions

Security fixes target the latest `main` revision on the documented Windows
platform. The project is in development; its package version is not a promise of
a maintained release line. Older commits, forks and separate release branches
receive no promised backports. Update to current `main` and locked dependencies
when assessing whether an issue is already fixed.

## Report privately

Contact **Björn Rudner** at [rudnerbjoern@hotmail.com](mailto:rudnerbjoern@hotmail.com)
with the subject **Ride Forces Analyzer security report**.
If GitHub offers **Report a vulnerability** on the repository's
[Security Advisories page](https://github.com/rudnerbjoern/ride-forces-analyzer/security/advisories),
you may use that private channel instead. Its availability depends on repository
settings; this policy does not assert it is enabled.

Do not disclose vulnerabilities, working exploits, credentials or private
recordings in public issues, pull requests or discussions. For an initial email,
provide a concise description without live secrets or sensitive attachments;
coordinate a suitable transfer method if additional private evidence is needed.

Include:

- Affected revision/version, Windows version and relevant dependency or FFmpeg version.
- Reproduction steps, expected/actual behavior and likely security impact.
- A minimal synthetic example where possible, and any suggested mitigation.

Relevant examples include unsafe `.forces` parsing, command execution through
export inputs, unintended file writes or exposure of private recording data.
For ordinary bugs and feature requests, use the normal issue templates.

Reports are handled on a best-effort basis without guaranteed response or fix
deadlines. Please coordinate public disclosure with the maintainer while the
report is assessed and a fix is prepared. Nothing here promises a bug bounty.
