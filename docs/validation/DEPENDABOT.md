# Node dependency security follow-up — 2026-10-13

This follow-up addresses development-tool dependencies after the authorized merge
of [PR #2](https://github.com/rudnerbjoern/ride-forces-analyzer/pull/2), commit
`a70c3e7ed44a737610e6647e82a4c1e273c2a8c5`. The Python application does not use
these Node modules. No M2 feature or recording interpretation is added.

## Applied dependency decisions

- **smol-toml 1.8.0 → 1.9.1:** the medium-severity quadratic key-parsing advisory
  is fixed starting with 1.9.0. markdownlint-cli2 pins 1.8.0 exactly; CSpell also
  consumes this parser. A root override updates both consumers. Ordinary named
  npm updates did not change the vulnerable version.
  [Vendor advisory](https://github.com/squirrelchat/smol-toml/security/advisories/GHSA-r4xh-jqrq-34v2).
- **KaTeX 0.16.47 → 0.19.0:** the low-severity inherited `trust` advisory is fixed
  starting with 0.18.2. The override is restricted to micromark-extension-math,
  whose declared `^0.16.0` range excludes the fix. This deliberately crosses its
  dependency range; compatibility is covered by the contracts below, not assumed
  for every KaTeX feature. Actual exploitation also requires prototype pollution
  and inserting rendered HTML into a browser.
  [Vendor advisory](https://github.com/KaTeX/KaTeX/security/advisories/GHSA-238p-pmpm-9mq7).

These were the latest stable fixed releases returned by the npm registry on the
report date. Direct development-tool pins remain unchanged. The lockfile also
updates Commander from 8.3.0 to 15.0.0 and removes its duplicate CSpell copy.
Commander requires Node ≥22.12.0, below the project's ≥22.18.0 minimum.
The three updated packages declare no installation lifecycle scripts.

Context7 was used to check root-only overrides and npm audit behavior against
the [npm override documentation](https://docs.npmjs.com/cli/v11/configuring-npm/package-json#overrides)
and [npm audit documentation](https://docs.npmjs.com/cli/v11/commands/npm-audit).
Review these overrides when upstream consumers update their pins; remove an
override only after the resolved lock remains patched and the suites pass.

## Open high-severity advisory

**braces 3.0.3 remains open:** GHSA-vfj7-8cjw-p6xm, CVE-2026-93687. The registry's
latest release is 3.0.3 and GitHub lists no patched version on the report date.
The dependency is reached through development-tool glob matching, including
markdownlint-cli2 → micromatch → braces.
[GitHub advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).

A bounded Windows child-process probe reproduced `RangeError` from stack
exhaustion at 4,500 nesting levels / 9,001 characters, below the package's
10,000-character limit. The [maintainer disputes the advisory](https://github.com/micromatch/braces/issues/70);
this does not invalidate the observed reproduction. Current project globs are
small configured patterns; no application API accepts arbitrary glob patterns.
That limits exposure but does not fix the vulnerable package.

No alert was dismissed. A vendor fix, maintained replacement or input-depth
guard requires a separate review. npm's current automated proposal downgrades
markdownlint-cli2 to 0.21.0 and marks it as a major change; do not apply
`npm audit fix --force` without reviewing the resulting tool behavior.

## Regression scope and environment

`npm run test:dependencies` runs six offline Node tests from
`tests/dependencies/security.test.mjs` in the Windows quality job:

- Both actual TOML consumers parse 2,048 flat keys and nested configuration.
  This checks compatibility, not a performance guarantee or full denial-of-service proof.
- KaTeX rejects an inherited `trust` setting for a JavaScript link. This test
  failed against the original installation; no HTML is inserted into a browser.
- micromark renders three mathematical expressions through the overridden KaTeX.

Resolution starts at each actual consumer rather than assuming npm hoists a
package to the root. No direct development dependency was added for these tests.
The existing documentation suite also exercises the updated markdownlint and
CSpell CLIs against the repository.

The isolated feasibility checks passed under native Windows Node 26.11.1 /
npm 11.20.0 and the installed global Node 26.10.0 / npm 11.19.1. The project and
CI pin remains 26.11.1; prefer that version on the developer PATH. Editor extension
bundles were not changed or audited by this Node lockfile update.

The candidate audit reduced three distinct advisories to one. npm's aggregated
affected-package count fell from nine to five, all in the remaining high-severity
braces chain. `npm audit` still exits 1; the audit is not clean. CI runs the offline
regression suites rather than suppressing this advisory to create a passing audit gate.

## Root-environment verification

The updated root installation passed native Windows checks with the project-pinned
Node 26.11.1 / npm 11.20.0 and Python 3.14.6:

- Offline `npm ci --no-audit --no-fund` installed 195 packages with normal lifecycle rules.
- All six dependency regressions passed. The inherited-trust case failed before
  the update and passed afterward. smol-toml now returns tables without
  `Object.prototype`; parser tests compare the actual configuration data.
- `uv lock --check`, Ruff lint and formatting (14 files), strict mypy (10 source
  files), Pyright (14 analyzed files) and three static typing contracts passed.
- All 39 pytest cases passed on win32, including both native GUI tests.
- All 17 Markdown files passed lint and local-link checks; CSpell checked 42 files
  with zero issues. Installed quality suites ran with npm offline.
- actionlint 1.7.12 accepted the PR-only workflow, including the new test step.
- All four recording byte lengths and SHA-256 values match their original snapshots.
- A fresh root `npm audit --json` confirmed only the braces advisory, with five
  affected packages and exit code 1. smol-toml and KaTeX are absent from the findings.

GitHub-hosted verification is pending publication of this branch. The default-branch
Dependabot alerts remain separate from the local patched lock until integration.
No alert has been dismissed, and this branch does not claim a clean security audit.
