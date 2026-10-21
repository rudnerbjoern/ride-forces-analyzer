# Dependencies and update policy

Configuration is authoritative. This guide neither duplicates lock contents nor
claims dependencies are latest or vulnerability-free.

Windows remains the development host. The same Python lock supplies Linux x64
and macOS x64/arm64 native release workers; no additional Python runtime dependency
is introduced. Linux desktop shared libraries and an external FFmpeg are target
OS requirements, not bundled GyanD downloads. The
[release guide](RELEASE.md#linux-and-macos-packages) owns installation commands,
platform baselines and native validation.

| Scope                       | Source of truth                                                                  |
| --------------------------- | -------------------------------------------------------------------------------- |
| Python runtime              | [.python-version](../../.python-version), [pyproject.toml](../../pyproject.toml) |
| Python packages/hashes      | [uv.lock](../../uv.lock)                                                         |
| Build backend               | `build-system` in pyproject.toml                                                 |
| Node runtime                | [.node-version](../../.node-version)                                             |
| Development tools/overrides | [package.json](../../package.json), [package-lock.json](../../package-lock.json) |
| FFmpeg archive/checksum     | [ffmpeg.json](../../ffmpeg.json)                                                 |
| GitHub Actions              | [.github/workflows](../../.github/workflows)                                     |

- [Setup](SETUP.md) installs locked dependencies. Node is development-only;
  installed optional packages do not establish features; see [roadmap](../ROADMAP.md).
- Architecture owns [library roles/rationale](../architecture/09_architecture_decisions.md#analysis-models-and-libraries)
  and [runtime/rendering/storage dependencies](../architecture/07_deployment_view.md).
- Development-only `coverage.py`/`pytest-cov` provide the
  [recording/service coverage gate](CODE_QUALITY.md#recording-model-and-service-coverage)
  and VS Code pytest coverage integration.
- Standalone redistribution requires actual assembled notices;
  [third-party inventory](../../THIRD_PARTY_NOTICES.md) owns Qt Charts/FFmpeg terms,
  fonts/materials and outstanding source/notice duties.

## Dependency updates

[Dependabot YAML](../../.github/dependabot.yml) configures native GitHub updates
after integration into default branch `main`; no scheduled Actions workflow is needed.
Dependabot creates branches/PRs, without direct pushes to `main` or automatic merging.
[CI guide](CI.md) owns PR checks, manual CI and source-tag validation.

### Project policy

Weekly Monday schedule, Europe/Berlin; requested start times, not execution guarantees:

| Ecosystem        | Time  | Inputs                                                               |
| ---------------- | ----- | -------------------------------------------------------------------- |
| `uv`             | 08:00 | pyproject.toml / uv.lock: runtime, development and optional packages |
| `npm`            | 08:15 | package.json / package-lock.json                                     |
| `github-actions` | 08:30 | Action references in .github/workflows/                              |

- Group minor/patch versions per ecosystem; separate major PRs. SemVer categories
  do not guarantee compatibility.
- Limit version-update PRs to three per ecosystem; seven-day cooldown for new
  versions. Security updates bypass that schedule/cooldown/version-PR limit when enabled.
- Group security fixes separately per ecosystem, allowing major fixes when needed.
- Preserve compatible requirements when possible; update resolved locks.
  Existing exact npm pins stay exact.
- No wildcard ignore, custom target branch, private-registry credentials,
  suppressed alerts or automatic merge configured.
- These are project choices, not mandatory GitHub defaults. Updates still require
  owner review, native Windows validation, applicable CI and explicitly authorized merge.
  Bot proposals prove neither compatibility nor a clean audit.

### Security settings and limits

- Enable dependency graph, alerts and automatic security updates in repository
  settings. YAML schedules target `main` but do not establish current service-side
  settings or dismiss alerts.
- Retain reviewed overrides below until upstream resolution/tests justify changes.
  Advisories without compatible fixes cannot be guaranteed automatic fixes.
- Maintain interpreter/uv pins, action input versions such as setup-uv's
  `with.version`, editor extensions and documentation versions separately;
  Actions updates cover action references.
- A successful hosted updater run must establish support for current Python
  constraints/lock revision; local tests cannot establish it.

### Node overrides and security boundary

| Override / pin                                                             | Reason                                                                                                                                                                           |
| -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `smol-toml` 1.9.1                                                          | [Quadratic TOML parsing](https://github.com/squirrelchat/smol-toml/security/advisories/GHSA-r4xh-jqrq-34v2)                                                                      |
| `micromark-extension-math` → KaTeX 0.19.0                                  | [Inherited trust handling](https://github.com/KaTeX/KaTeX/security/advisories/GHSA-238p-pmpm-9mq7); crosses consumer's declared range, covered by real-consumer regression tests |
| `markdownlint-cli2` → markdown-it 15.0.3; direct parser pinned identically | [Smart-quote processing](https://github.com/markdown-it/markdown-it/security/advisories/GHSA-r7fv-28h4-cvq7)                                                                     |

- Manifest/lock retain these pins. Real-consumer tests cover project compatibility,
  not all possible consumers.
- markdown-it 15.0.3 also fixes
  [quadratic reference parsing](https://github.com/markdown-it/markdown-it/security/advisories/GHSA-gfr2-rv44-r23c).
  Both the direct parser and markdownlint's parser must use the patched release.
- Deep glob nesting can exhaust the [braces parser stack](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
  Project globs are small configured patterns; no application API accepts arbitrary globs.
- Current advisories/fix availability require a fresh audit, including before release.
  Compatibility checks do not establish a clean audit or cover editor bundles/native Python binaries.

### Local checks

```powershell
npm run test:dependencies
node --test tests/ci/changes.test.mjs
npm run test:docs
```

Policy tests reuse locked CSpell's YAML parser without new dependencies: ecosystem
coverage, security/major separation, schedules, read-only PR CI and override protection.
They do not fully validate GitHub's service-side schema.
[CI guide](CI.md#verification-boundaries) owns routing/hosted-verification limits.

### Primary references

- [Configuration options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
- [Supported ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories)
- [Security-update configuration](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-security-updates)
- [PR volume and cooldown](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/optimizing-pr-creation-version-updates)
