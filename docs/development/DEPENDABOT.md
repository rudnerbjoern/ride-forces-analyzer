# Dependabot update policy

The native [.github/dependabot.yml](../../.github/dependabot.yml) schedules version
updates through GitHub Dependabot. A separate scheduled Actions workflow is not
needed; project CI remains PR-only. Configuration takes effect after integration
into the default branch, `main`. Dependabot creates its own update branches/PRs;
it does not push directly to `main` or merge changes.

## Project policy

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

These scheduling/grouping/cooldown choices are project decisions, informed by
GitHub documentation and Context7; they are not mandatory GitHub defaults.
Dependency updates still need owner review, native Windows validation and passing
applicable [CI checks](CI.md) before an explicitly authorized merge. Bot proposals
are not evidence of compatibility or a clean security audit.

## Security settings and limits

GitHub's security-update setting is separate from the YAML version-update schedule.
Enable Dependabot alerts/dependency graph and automatic security updates in
repository settings. The recorded 2026-10-13 setup check reports alerts enabled and automatic security
updates `enabled=true, paused=false`. This is scoped configuration evidence,
not a fresh service-side verification. The YAML schedule targets `main`.
No alert is dismissed by this configuration.

Keep the reviewed smol-toml and scoped KaTeX overrides until upstream resolution
and tests justify changing them; see the dated [security audit](../validation/DEPENDABOT.md).
An advisory without an available compatible fix cannot be guaranteed an automatic
fix. uv/Python/Node interpreter pins, action input versions such as setup-uv's
`with.version`, editor extensions and documentation version references still need
coordinated maintenance; the Actions ecosystem updates action references.
The first actual uv updater run must confirm support for the project's current
Python constraints and lock revision. Local tests do not prove hosted updater success.

## Local checks

```powershell
npm run test:dependencies
node --test tests/ci/changes.test.mjs
npm run test:docs
```

Policy tests parse YAML using the already locked CSpell consumer, cover ecosystem
coverage, security/major-update separation, constrained schedules and read-only
PR CI, and protect existing security overrides. They add no dependencies and are
not a complete validation of GitHub's service-side configuration schema.
Recorded results remain in [developer-tool validation](../validation/DEVELOPER_TOOLS.md).

## Primary references

- [Configuration options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
- [Supported ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories)
- [Security-update configuration](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-security-updates)
- [PR volume and cooldown](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/optimizing-pr-creation-version-updates)
