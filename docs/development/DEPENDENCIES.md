# Dependencies and update policy

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

[Setup](SETUP.md) installs locked dependencies. Node is development
tooling, not an application runtime. Installed optional packages do not establish
product features; the [roadmap](../ROADMAP.md) owns that status.
The development-only `coverage.py` and `pytest-cov` dependencies supply the focused
recording-model/service [coverage measurement and gate](CODE_QUALITY.md#recording-model-and-service-coverage)
and VS Code's pytest coverage integration.

NumPy/Pint/SciPy support existing analysis boundaries; Pillow supports frame
rendering and Python's sqlite3 supports export configuration without a server.
[analysis library decision](../architecture/09_architecture_decisions.md#analysis-models-and-libraries) retains
scientific library rationale and binary-license limits.
[Node security policy](#node-overrides-and-security-boundary) does not replace a fresh
release audit. Standalone redistribution must inspect actual assembled notices.
The [third-party license inventory](../../THIRD_PARTY_NOTICES.md) records inspected
Qt Charts/FFmpeg terms, fonts/materials and outstanding notice/source duties.

## Dependency updates

The native [.github/dependabot.yml](../../.github/dependabot.yml) schedules version
updates through GitHub Dependabot. A separate scheduled Actions workflow is not
needed; dependency proposals use the existing PR checks. Manual CI and source-tag
validation are described in the [CI guide](CI.md). Configuration takes effect after integration
into the default branch, `main`. Dependabot creates its own update branches/PRs;
it does not push directly to `main` or merge changes.

### Project policy

- `uv`: `pyproject.toml` and `uv.lock`, including runtime, development and optional
  dependency declarations; Monday at 08:00 Europe/Berlin.
- `npm`: `package.json` and `package-lock.json`; Monday at 08:15 Europe/Berlin.
- `github-actions`: action references in `.github/workflows/`; Monday at 08:30
  Europe/Berlin. The schedule is a requested start time, not an execution guarantee.
- Group minor/patch version updates per ecosystem. Major version updates remain
  separate PRs; a SemVer category does not guarantee compatibility.
- Allow at most three open version-update PRs per ecosystem. Seven-day cooldown
  for newly released versions reduces churn; it does not delay security updates.
- Group security fixes separately per ecosystem, including major fixes when
  required. Security PRs are independent of the weekly version-update schedule
  and version-PR limit, provided repository security updates are enabled.
- Preserve compatible version requirements when possible; update resolved locks.
  Existing exact npm pins remain exact. No wildcard ignore, custom target branch,
  private-registry credentials, suppressed alerts or automatic merge is configured.

These scheduling/grouping/cooldown choices are project decisions, not mandatory
GitHub defaults.
Dependency updates still need owner review, native Windows validation and passing
applicable [CI checks](CI.md) before an explicitly authorized merge. Bot proposals
are not evidence of compatibility or a clean security audit.

### Security settings and limits

GitHub's security-update setting is separate from the YAML version-update schedule.
Enable Dependabot alerts/dependency graph and automatic security updates in
repository settings; the YAML alone does not establish their current service-side
state. The YAML schedule targets `main`.
No alert is dismissed by this configuration.

Keep the reviewed smol-toml and scoped KaTeX overrides until upstream resolution
and tests justify changing them.
An advisory without an available compatible fix cannot be guaranteed an automatic
fix. uv/Python/Node interpreter pins, action input versions such as setup-uv's
`with.version`, editor extensions and documentation version references still need
coordinated maintenance; the Actions ecosystem updates action references.
Support for the project's current Python constraints and lock revision requires
a successful hosted updater run; local tests cannot establish that outcome.

### Node overrides and security boundary

Node is development tooling, not an application runtime dependency.
`package.json` and `package-lock.json` retain smol-toml 1.9.1 for
[its security fix](https://github.com/squirrelchat/smol-toml/security/advisories/GHSA-r4xh-jqrq-34v2)
and scoped KaTeX 0.19.0 for
[inherited trust handling](https://github.com/KaTeX/KaTeX/security/advisories/GHSA-238p-pmpm-9mq7).
The KaTeX override crosses the consumer's declared range; real-consumer regression
tests cover compatibility within this project.

The scoped `markdownlint-cli2` override also requires markdown-it 15.0.2 for the
[smart quote processing fix](https://github.com/markdown-it/markdown-it/security/advisories/GHSA-r7fv-28h4-cvq7).
The direct documentation-parser dependency remains pinned to the same version.

Deeply nested glob patterns can exhaust the braces parser stack
([advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)). Project globs are
small configured patterns; no application API accepts arbitrary glob input.
Current advisory and fix availability require a fresh audit. Compatibility tests
do not establish a clean security audit or cover editor extension bundles and
native Python binaries.

### Local checks

```powershell
npm run test:dependencies
node --test tests/ci/changes.test.mjs
npm run test:docs
```

Policy tests parse YAML using the already locked CSpell consumer, cover ecosystem
coverage, security/major-update separation, constrained schedules and read-only
PR CI, and protect existing security overrides. They add no dependencies and are
not a complete validation of GitHub's service-side configuration schema.
The [CI guide](CI.md) owns routing and hosted-verification boundaries.

### Primary references

- [Configuration options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
- [Supported ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories)
- [Security-update configuration](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-security-updates)
- [PR volume and cooldown](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/optimizing-pr-creation-version-updates)
