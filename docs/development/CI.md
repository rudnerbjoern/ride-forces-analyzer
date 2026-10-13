# Pull-request CI selection

CI provides secondary validation after complete local acceptance. The workflow
starts only on `pull_request`, with read-only repository permissions and no new
tool dependencies. All jobs use native Windows.

## Dependency check and routing

`dependency-check` runs the [selection tests](../../tests/ci/changes.test.mjs) with
Node built-ins, then evaluates the full PR diff using `git diff base...head`.
Full history avoids incomplete comparisons. NUL-delimited names preserve spaces;
disabled rename detection includes both old and new paths. Missing revisions,
Git failures or invalid outputs fail validation rather than silently skipping tests.

The [selector](../../.github/scripts/ci-changes.mjs) exposes boolean job outputs:

- `documentation`: any `.md` path, including repository instructions, Markdown
  under source/tests, deletions and renames. Markdown-only PRs skip `code`.
- `code`: non-Markdown source/tests, fixtures, executable scripts, workflow files
  and runtime/dependency inputs (`pyproject.toml`, `uv.lock`, Python/Node version
  files, npm manifests/lock, Git/editor configuration and VS Code settings).
  Dependabot configuration changes also select code checks and dependency policy tests.
  Tests, fixtures and environment changes can invalidate code evidence even when
  application source is unchanged.
- Mixed changes run both suites. Unrelated assets run neither suite.

Selection uses the entire PR, not just its latest commit. A later Markdown-only
commit on an unmerged code PR still leaves that PR's code changes selected.
No previous-run cache or implicit transfer of CI results is introduced.

Per owner policy, documentation tests run only for Markdown changes: changes to
Markdown/CSpell configuration alone do not select that suite. Their local checks
remain mandatory. Test helper code changes select `code`; documentation helper
behavior must also be checked locally before publication.

## Jobs and required checks

`code` installs locked dependencies and runs Ruff lint/format, mypy, Pyright,
type contracts, Node dependency regressions and pytest. For code-only PRs it also
runs CSpell; mixed PRs receive CSpell through `documentation`.
`documentation` installs locked Node tools and runs `npm run test:docs`.

Both jobs depend on successful detection and use job-level conditions. The final
`check` job always evaluates their results: a selected suite must succeed; an
unselected suite must be skipped. Failed/cancelled detection or selected jobs
fail the gate. Keep `check` required in branch protection; it retains the existing
check name. A skipped `documentation` check is expected for non-Markdown PRs.
Do not apply workflow-level skip filters that prevent required statuses appearing.
GitHub documents this distinction in its
[job condition rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions).

## Local verification and limits

From the repository root with the configured native Windows Node executable:

```powershell
node --test tests/ci/changes.test.mjs
```

Tests cover Markdown-only, code-only and mixed inputs, locks/configuration,
empty/unrelated changes, invalid revisions, output generation and real synthetic
Git histories with renames, deletions, divergent bases and cumulative changes.
All synthetic repositories live under `.tmp/`; original fixtures are never written.

Native Windows verification on 2026-10-13: the command above passed 33 tests,
including 13 scenarios for the actual PowerShell gate in the workflow.
`.tmp/m1-actionlint/actionlint.exe .github/workflows/ci.yml` passed with actionlint
1.7.12. `npm run test:docs` passed 33 link tests, Markdownlint checked 33 files
with zero issues and CSpell checked 86 files with zero issues.

Workflow syntax must also pass actionlint and changed documentation must pass
`npm run test:docs`. Hosted conditional execution and current branch-protection
settings remain unverified until an authorized PR run and settings inspection.
