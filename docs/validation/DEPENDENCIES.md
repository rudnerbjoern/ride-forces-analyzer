# Dependency inventory and boundaries

Repository configuration is authoritative; this page does not duplicate lock
contents or claim that dependencies are latest or vulnerability-free.

| Scope                         | Source of truth                                                                  |
| ----------------------------- | -------------------------------------------------------------------------------- |
| Python runtime                | [.python-version](../../.python-version), [pyproject.toml](../../pyproject.toml) |
| Python packages and hashes    | [uv.lock](../../uv.lock)                                                         |
| Build backend                 | `build-system` in pyproject.toml                                                 |
| Node runtime                  | [.node-version](../../.node-version)                                             |
| Development tools / overrides | [package.json](../../package.json), [package-lock.json](../../package-lock.json) |
| FFmpeg archive / checksum     | [ffmpeg.json](../../ffmpeg.json)                                                 |
| GitHub Actions                | [.github/workflows](../../.github/workflows)                                     |

[Setup](../development/SETUP.md) installs locked dependencies. Node is development
tooling, not an application runtime. Installed optional packages do not establish
product features; the [roadmap](../ROADMAP.md) owns that status.

NumPy/Pint/SciPy support existing analysis boundaries; Pillow supports frame
rendering and Python's sqlite3 supports export configuration without a server.
[ADR 0004](../decisions/0004-analysis-contracts-and-library-policy.md) retains
scientific library rationale and binary-license limits.
[Node security evidence](DEPENDABOT.md) is dated and does not replace a fresh
release audit. Standalone redistribution must inspect actual assembled notices.
