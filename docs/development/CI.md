# Pull-request CI selection

CI is secondary validation after local acceptance. The read-only validation
workflow runs only on `pull_request`; all jobs use native Windows.

## Routing and required gate

`dependency-check` runs [selection tests](../../tests/ci/changes.test.mjs) and
classifies the complete `git diff base...head` through the
[selector](../../.github/scripts/ci-changes.mjs). Full history, NUL-delimited names
and disabled rename detection cover cumulative changes, deletions and both rename
paths. Missing revisions/Git failures/invalid outputs fail closed. No result cache
or reuse across hosted runs is introduced.

| Job             | Inputs / checks                                                                                                                                                                                                                   |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `documentation` | Any `.md` path, including deletion/rename, source/test Markdown and skill docs; installs Node tools and runs `npm run test:docs`                                                                                                  |
| `code`          | Non-Markdown source/tests/fixtures/scripts, workflows, Python/Node manifests/locks/version files, Git/editor settings, VS Code settings, Dependabot/label rules; runs application lint/format/types/contracts/dependencies/pytest |
| `skills`        | Non-Markdown skill files, consumed commit policy, Python manifest/lock/version, Git/editor settings and workflow/CI selector/tests; runs the skill's separate Ruff/mypy/pytest suite                                              |
| `check`         | Always evaluates detection and all selected results; selected jobs must succeed, unselected jobs must be skipped                                                                                                                  |

Markdown-only changes skip application tests. Skill-only implementation skips
application tests; ordinary application/Node-only changes skip skill tests. Mixed
changes select every affected suite. Commit-policy Markdown selects both docs and
skills. Code-only/skill-only jobs also run CSpell; mixed PRs get it from docs.
The current PR diff remains authoritative after later documentation-only commits.

Per owner policy, Markdown/CSpell configuration alone does not select docs;
affected local checks are still required. Documentation-test helpers under `tests/`
select code and also need affected local documentation checks. Empty/unrelated
changes select no suite, with successful detection still required.

Keep `check` required in branch protection. Failed/cancelled detection or selected
jobs block merge; unknown/inconsistent results cannot count as success. Avoid
workflow-level path skips that leave required statuses absent. See
[GitHub job conditions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions).

## Issue templates and additive PR labels

[Bug](../../.github/ISSUE_TEMPLATE/bug_report.md) and
[feature](../../.github/ISSUE_TEMPLATE/feature_request.md) templates assign `bug`
and `enhancement`. The [PR template](../../.github/pull_request_template.md) asks
for scope, actual local validation and review. Templates become active on `main`
and do not rewrite existing issues/PRs.

[Label rules](../../.github/labeler.yml) assign `documentation` for Markdown,
`dependencies` for manifests/locks/Dependabot, and `ci` for workflows/CI scripts,
tests or label rules. Existing labels are preserved; `dependencies` and `ci` were
created with owner authorization. Priority/scientific review stays manual.

The separate [labeler workflow](../../.github/workflows/labeler.yml) uses trusted
configuration via `pull_request_target` for opened/synchronized/reopened PRs to
`main`, including drafts/forks/Dependabot. It performs no checkout or PR-code
execution and uses no custom secrets. Permissions are `contents: read` and
`pull-requests: write`; labels must already exist. `sync-labels: false` preserves
manual/previous labels. Labels neither approve nor merge. The validation workflow
remains read-only/PR-only; no scheduled workflow or new dependency is introduced.

## Verification boundaries

[Setup](SETUP.md) lists exact local commands. CI tests cover cumulative synthetic
Git histories, Unicode/spaces/renames/deletions, invalid revisions, output routing
and the actual PowerShell gate, using `.tmp/` repositories. Dependency tests cover
templates, label rules and permissions; actionlint checks workflow syntax.
These checks do not prove hosted label assignment, hosted conditional execution
or current branch protection. Fresh hosted outcomes require an authorized PR run
and read-only settings inspection; they belong in the PR metadata.

References: [issue templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository),
[Labeler](https://github.com/actions/labeler),
[PR target events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_target).
