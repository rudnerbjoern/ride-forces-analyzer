# Pull-request CI selection

CI provides secondary validation after complete local acceptance. The validation workflow
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
  Label-rule changes select code checks and label policy tests.
  Tests, fixtures and environment changes can invalidate code evidence even when
  application source is unchanged.
- `skills`: non-Markdown files under `.agents/skills/`, the commit policy consumed
  by the helper, Python configuration/lock/version, Git/editor configuration and
  CI workflows, selection scripts/tests. These inputs can invalidate skill evidence.
  Ordinary application source/tests and Node-only dependency changes skip this job.
  Skill Markdown alone selects documentation; commit-policy Markdown selects both
  documentation and skills because it changes the helper's validation contract.
- Skill-only implementation changes skip application tests. Mixed changes run each
  affected suite. Unrelated assets run none.

Selection uses the entire PR, not just its latest commit. A later Markdown-only
commit on an unmerged code PR still leaves that PR's code changes selected.
No previous-run cache or implicit transfer of CI results is introduced.

Per owner policy, documentation tests run only for Markdown changes: changes to
Markdown/CSpell configuration alone do not select that suite. Their local checks
remain mandatory. Helper code changes under `tests/` select `code`; documentation helper
behavior must also be checked locally before publication.

## Jobs and required checks

`code` installs locked dependencies and runs Ruff lint/format, mypy, Pyright,
type contracts, Node dependency regressions and pytest. For code-only PRs it also
runs CSpell; mixed PRs receive CSpell through `documentation`.
`documentation` installs locked Node tools and runs `npm run test:docs`.
`skills` installs locked Python dependencies and runs Ruff lint/format, mypy and
`uv run pytest .agents/skills/github-delivery/tests`. Its tests use isolated Git
repositories, are deliberately separate from application pytest/Test Explorer
discovery and are never rerun solely to publish unchanged skill code.
For skill-only PRs this job also runs CSpell; other PRs receive spelling checks
through the selected application or documentation job.

All three jobs depend on successful detection and use job-level conditions. The final
`check` job always evaluates their results: a selected suite must succeed; an
unselected suite must be skipped. Failed/cancelled detection or selected jobs
fail the gate. Keep `check` required in branch protection; it retains the existing
check name. A skipped `documentation` check is expected for non-Markdown PRs.
Do not apply workflow-level skip filters that prevent required statuses appearing.
GitHub documents this distinction in its
[job condition rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions).

## Issue templates and PR labels

The [bug report](../../.github/ISSUE_TEMPLATE/bug_report.md) assigns `bug` and
the [feature request](../../.github/ISSUE_TEMPLATE/feature_request.md) assigns
`enhancement`. The [PR template](../../.github/pull_request_template.md) asks for
scope, actual local validation and review checks. Templates become available after
integration into `main`; existing issues and PR bodies are not rewritten.

Keep the label set small:

| Label           | Assignment                                                            |
| --------------- | --------------------------------------------------------------------- |
| `bug`           | Bug report template or manual review                                  |
| `enhancement`   | Feature request template or manual review                             |
| `documentation` | PR changes to any Markdown file                                       |
| `dependencies`  | PR changes to Python/npm manifests, locks or Dependabot configuration |
| `ci`            | PR changes to workflows, CI scripts/tests or label rules              |

Existing GitHub labels are preserved. Missing `dependencies` and `ci` labels were
created with owner authorization; template/action labels must already exist.
Priority and scientific assessment remain manual. Labels do not grant approval
or permit merging, and label automation never merges PRs.

The separate [label workflow](../../.github/workflows/labeler.yml) uses
`actions/labeler` and [path rules](../../.github/labeler.yml) on opened, synchronized
or reopened PRs targeting `main`, including drafts. `pull_request_target` permits
metadata updates for fork and Dependabot PRs using trusted repository configuration.
The single step has no checkout, scripts, PR code execution or custom secrets.
Permissions are limited to `contents: read` and `pull-requests: write`; all labels
are pre-created, so no `issues: write` permission is required. `sync-labels: false`
preserves manual labels and previously assigned labels when matching files are
later removed. Labels are additive descriptions, not a merge gate.

The existing validation workflow remains read-only and `pull_request`-only.
No scheduled workflow or additional package dependency is introduced.
`npm run test:dependencies` checks template metadata, representative path matches
and workflow permissions. Actionlint and documentation checks validate local files;
they do not prove hosted label assignment. The initial workflow/configuration must
reach `main` before GitHub can run it; its hosted execution remains unverified.

References: [GitHub issue templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository),
[Labeler](https://github.com/actions/labeler) and
[PR target events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_target).

## Local verification and limits

From the repository root with the configured native Windows Node executable:

```powershell
node --test tests/ci/changes.test.mjs
```

Tests cover Markdown-only, code-only and mixed inputs, locks/configuration,
empty/unrelated changes, invalid revisions, output generation and real synthetic
Git histories with renames, deletions, divergent bases and cumulative changes.
All synthetic repositories live under `.tmp/`; original fixtures are never written.

Native Windows verification on 2026-10-13: the command above passed 39 tests,
including 31 scenarios for the actual PowerShell gate in the workflow. They cover
all eight valid combinations of selected application/documentation/skill jobs and
reject missing, failed, cancelled and inconsistent skill results.
`.tmp/m1-actionlint/actionlint.exe .github/workflows/ci.yml` passed with actionlint
1.7.12. Documentation checks are recorded in the [skill verification](CODEX.md).

Workflow syntax must also pass actionlint and changed documentation must pass
`npm run test:docs`. Hosted conditional execution and current branch-protection
settings remain unverified until an authorized PR run and settings inspection.
