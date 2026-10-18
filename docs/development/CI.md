# Pull-request CI selection

CI is secondary validation after local acceptance. The read-only validation
workflow runs on pull requests targeting `main` and on manual dispatch; all jobs
use native Windows. Manual dispatch selects all three suites without PR SHAs.
The same workflow is reusable by source-release validation with all suites enabled.
Every run additionally requires the independent secret-scanning job.
Pinned tool downloads retry all transfer errors three times, with 30-second
connection and 120-second per-attempt limits. TLS certificate/revocation checks
and archive SHA-256 verification remain mandatory; exhausted retries fail the job.
Every checkout pins the event commit SHA, or the explicit immutable `revision`
provided by a reusable release call. Release preparation resolves and validates
the tag commit before passing it to the full CI suite; package builds and
publication remain gated on that suite's success for the same commit.
There is no duplicate CI run on pushes to `main`.

New PR pushes cancel older runs of the same workflow and PR. Manual runs have
independent concurrency groups and are not cancelled by another run. Job time limits are
15 minutes for application checks, 10 for delivery skills, workflow validation and secret scanning, and 5 each for change
selection, documentation and the final gate. Python commands use locked dependency
resolution throughout.

Both pytest jobs print skip/failure reasons and their 20 slowest test phases.
Completed test commands, including failures, upload only their JUnit XML report
for 14 days; skipped or cancelled test jobs do not upload reports. Application and
skill artifacts are separate. Missing expected reports fail the upload; test failures
remain failures. Full logs, recordings, databases and screenshots are not uploaded.

## Routing and required gate

`dependency-check` runs [selection tests](../../tests/ci/changes.test.mjs) and
classifies the complete `git diff base...head` through the
[selector](../../.github/scripts/ci-changes.mjs). Full history, NUL-delimited names
and disabled rename detection cover cumulative changes, deletions and both rename
paths. Missing revisions/Git failures/invalid outputs fail closed. No result cache
or reuse across hosted runs is introduced.

| Job             | Inputs / checks                                                                                                                                                                                                                   |
| :-------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gitleaks`      | Every PR, manual and reusable run; checksum-pinned scanner validates itself and scans complete fetched Git history                                                                                                                |
| `actionlint`    | Workflow/script/CI-test and dependency-test changes, plus manual/reusable full runs; validate all workflows with checksum-pinned actionlint                                                                                       |
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

## Required secret scanning

The Windows x64 Gitleaks 8.30.1 download is pinned by SHA-256. Checkout fetches
complete history at the event SHA; `git --log-opts=--all` scans all fetched refs.
The scanner uses its default rules through an explicit generated configuration,
an empty ignore file and disabled inline allow comments. Repository-local scanner
configuration or ignore files cannot silently suppress findings. Reports and logs
use full redaction; the report remains under `.tmp/gitleaks/` without artifact upload.

A self-test requires clean synthetic history to pass and a deleted synthetic
token to fail, with redacted report/output even when its line has an allow comment.
Findings, scanner errors, failed self-tests, cancelled or skipped scans block the
final `check`, independently of the selected application/documentation suites.
The reusable full CI therefore blocks source release publication on scan failure.

This covers fetched Git history, not unreachable objects, uncommitted local files,
hosted issue/PR text or external assets. A passing rule-based scan is not proof
that no secret exists; [publication review](../../SECURITY.md#publication-boundary)
still applies.

## Workflow validation

The Windows x64 actionlint 1.7.12 archive is pinned by SHA-256 and checked before
extraction. Workflow files, `.github/scripts/`, `tests/ci/` and
`tests/dependencies/` select validation of all current workflows. Manual dispatch
and reusable full CI always select it. The final gate rejects failed, cancelled,
missing or unexpectedly skipped validation; legitimately unselected jobs must be
skipped. Source publication inherits this gate through full CI.

actionlint checks workflow structure and expressions; optional ShellCheck and
Pyflakes integrations are explicitly disabled. It does not execute embedded
PowerShell or prove hosted permissions and runtime behavior. The separate workflow
regression tests exercise the actual merge gate and release command with mocks.

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
remains read-only; no scheduled workflow or new runtime dependency is introduced.

## Source release tags

The separate [source-release workflow](../../.github/workflows/source-release.yml)
runs for pushed `v*` tags with read-only permissions. It first calls the full CI
for that tag revision; a failed, skipped or cancelled quality run blocks the source
job. The source job has a ten-minute limit and verifies that the tag equals `v`
plus `project.version`, checks required license
and setup files, rejects local/binary artifacts, and verifies original recording
bytes/hashes against the fixture inventory in a Git source ZIP. It also builds
the Python wheel and source distribution. Only the verified Git source ZIP and its
SHA-256 file and prepared release notes are retained as direct-download Actions artifacts for 14 days,
without an additional ZIP wrapper; the Python packages
are build checks. Runs for different tags remain independent.

A separate read-only Windows job (30-minute limit) installs the locked build group,
checks binary redistribution inputs, builds the standalone EXE and standard/complete
ZIPs, and executes all three with isolated preferences and a restricted PATH. Its
outputs include checksums and corresponding sources. Publication depends on this
job as well as full quality/source checks. Missing provider sources are documented
and reported; missing or modified catalog-listed archives fail verification. See
[Windows package scope and open inputs](RELEASE.md#windows-packages).

After source validation, a separate publication job attaches the ZIP/checksum to
a GitHub release together with the verified Windows downloads, their checksum file
and corresponding-source archive. It alone has `contents: write`, plus artifact read permission.
The [release policy](RELEASE.md) defines main ancestry, merged-PR and version gates,
prerelease classification and maintained release notes. No job creates tags or
changes repository visibility. This does not replace pre-release application/GUI validation or test
installation on a clean Windows machine. Existing tags do not trigger a run
retroactively. Release checks apply after the workflow is integrated and a new
tag is pushed.

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
