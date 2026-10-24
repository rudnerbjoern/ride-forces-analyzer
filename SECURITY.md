# Security policy

## Publication boundary

- Before publication, review current files and complete reachable Git history for
  credentials, private files and unintended personal information, including image metadata.
- Separately review release assets, CI logs and other hosted content; repository
  scans do not cover them automatically. Recheck new content; past scans give no continuing guarantee.
- Björn Rudner authorizes publication of his name and existing personal commit email.
  The [recording catalog](docs/development/RECORDINGS.md) owns permission for the
  authorized reference files, including GPS/metadata.
- These permissions cover neither additional private data nor third-party rights.
  Repository publication requires separate explicit owner authorization.

## Supported versions

- Security fixes target latest `main` on the documented
  [supported platforms](docs/architecture/02_architecture_constraints.md#technical-constraints).
- The project remains in development; package versions promise no maintained
  release line or backports for older commits, forks or separate release branches.
- Check current `main` and locked dependencies when assessing whether an issue is fixed.

## Report privately

- Contact **Björn Rudner**: [rudnerbjoern@hotmail.com](mailto:rudnerbjoern@hotmail.com).
  Subject: **Ride Forces Analyzer security report**.
- Alternatively, use **Report a vulnerability** on
  [Security Advisories](https://github.com/rudnerbjoern/ride-forces-analyzer/security/advisories)
  **if available**; this policy does not assert that repository feature is enabled.
- Never disclose vulnerabilities, working exploits, credentials or private recordings
  in public issues, PRs or discussions.
- Initial email: concise description, no live secrets/sensitive attachments.
  Coordinate transfer of additional private evidence separately.

Include:

- Affected revision/version, operating system and relevant dependency/FFmpeg version.
- Reproduction, expected/actual behavior and likely security impact.
- Minimal synthetic example where possible; suggested mitigation if available.

Relevant cases: unsafe `.forces` parsing, command execution through export inputs,
unintended writes or private recording exposure. Ordinary bugs/features use the
[issue templates](.github/ISSUE_TEMPLATE/).

Handling is best effort, without guaranteed response/fix deadlines or a promised
bug bounty. Coordinate public disclosure with the maintainer during assessment/fix preparation.
