# Pull-request CI selection

Architecture owns [local/hosted acceptance boundaries](../architecture/07_deployment_view.md#validation-and-release-boundary).
This guide defines workflow routing and gates; [setup](SETUP.md) owns local commands.

Development checks remain on Windows. The reusable
[native package workflow](../../.github/workflows/posix-packages.yml) additionally
builds and executes Linux x64 and macOS arm64/x64 packages on their own runners.
`posix` runs for application/shared inputs or changes to the CI/native package
workflows. The final `check` gate requires every selected target to succeed.
Each target has a 30-minute budget, uses locked dependencies, tests native platform
contracts and executes the extracted frozen app with a real CPU encode. Linux uses
Xvfb; macOS verifies app signatures. PR and manual CI runs build and verify packages
without uploading them. Only release calls enable `upload-packages`; verified
packages and their checksum files are then retained for 14 days for publication.
They contain neither recordings nor user databases.
These jobs qualify target packages; they do not add a Linux/macOS developer setup.

| Control                  | Contract                                                                                                                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Validation workflow      | [ci.yml](../../.github/workflows/ci.yml): read-only, Windows development checks and native Linux/macOS packages; PRs targeting `main`, manual dispatch, reusable release calls |
| Full runs                | Manual dispatch selects all suites/workflow validation without PR SHAs; release calls enable full checks for the resolved commit                                               |
| Mandatory scan           | Independent Gitleaks job on every validation run                                                                                                                               |
| Checkout                 | Event `github.sha` or supplied release `revision`; release jobs use the same validated tag commit                                                                              |
| Concurrency              | New PR pushes cancel older runs for that workflow/PR; manual runs have independent groups                                                                                      |
| Main pushes              | No duplicate validation run                                                                                                                                                    |
| Dependency resolution    | Locked Python commands throughout                                                                                                                                              |
| Scanner/linter downloads | Three retries for all transfer errors; 30 s connection / 120 s per attempt; TLS certificate/revocation and SHA-256 checks mandatory; exhausted retries fail                    |
| Time limits              | Non-UI application 15 min; UI/skills/actionlint/Gitleaks 10 min; detection/docs/final gate 5 min                                                                               |

All three pytest jobs use `-ra --durations=20`. Completed commands, including failures,
upload separate application/UI/skill JUnit XML artifacts for 14 days.
Skipped/cancelled jobs upload nothing; missing expected reports fail upload and
test failures remain failures. No full logs, recordings, databases or screenshots are uploaded.

## Routing and required gate

`dependency-check` runs [selector tests](../../tests/ci/changes.test.mjs), then
[ci-changes.mjs](../../.github/scripts/ci-changes.mjs) classifies cumulative
`git diff base...head`: full history, NUL-delimited paths, rename detection disabled
to include both rename paths and deletions. Missing revisions/Git failures/invalid
outputs fail closed. The independent `dependencies` selection runs the locked
Node/PowerShell dependency and workflow contracts inside `dependency-check`, even
when application checks are skipped. A contract failure fails that job and blocks
the merge gate. Hosted runs do not reuse test results.

| Job                | Selection / result                                                                                                                                                                                       |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gitleaks`         | Every run; checksum-pinned scanner self-test and complete fetched-history scan                                                                                                                           |
| `dependency-check` | Every run detects changes and tests the selector; selected `dependencies` additionally installs locked Node dependencies and runs `npm run test:dependencies`                                            |
| `actionlint`       | Workflow/script/CI-test/dependency-test and Dependabot/label/release-rule changes; manual/full reusable runs; validate all workflows                                                                     |
| `documentation`    | Any Markdown path, including source/tests/skills and deletions/renames; locked Node install and `npm run test:docs`                                                                                      |
| `code`             | Non-Markdown application/source/test/script and shared Python/Node/Git/editor inputs, excluding CI metadata and Node/PowerShell contracts; application lint/format/types and pytest excluding `tests/ui` |
| `ui`               | Same selection as `code`; complete `tests/ui` serially on a separate Windows runner                                                                                                                      |
| `posix`            | Application/shared inputs, `.github/workflows/ci.yml` or `.github/workflows/posix-packages.yml`; native Linux x64/macOS arm64/x64 build and runtime checks                                               |
| `skills`           | Non-Markdown skill implementation/tests, consumed commit policy, Python manifest/lock/version and Git/editor settings; separate skill Ruff/mypy/pytest                                                   |
| `check`            | Always evaluate detection, contract-selection validity and selected job results: selected = success, unselected = skipped                                                                                |

The `code`/`ui` jobs partition the complete application suite by directory and run
concurrently after selection; no timing-based exclusions. Both are required when
code is selected, including manual/release runs. UI tests remain serial per desktop.
A second Windows setup can reduce wall-clock waiting when runners are available;
it does not guarantee lower total runner minutes.

- Markdown-only and skill-only changes skip application tests. CI metadata,
  Node/PowerShell workflow contracts and selector changes select dependency/syntax
  checks without application/UI/skill tests. Changing the CI/native package workflow
  additionally selects POSIX. Python release-helper changes retain conservative
  application validation; shared toolchain/manifest inputs also retain full checks.
  Mixed changes select the union of affected suites.
- Commit-policy Markdown selects docs/skills. Code-only/skill-only runs supply
  CSpell; standalone dependency-contract runs also supply CSpell. Mixed runs with
  docs use its CSpell check.
- The complete PR diff remains authoritative after documentation-only follow-up commits.
- Markdown/CSpell configuration alone does not select docs. CSpell configuration
  changes select dependency contracts and the standalone `npm run spellcheck`
  path, without application/UI/POSIX builds. The dependency contracts run the real
  CSpell CLI against both translated catalogs, require rejection of injected
  German/French typos and verify dictionary scope outside the catalog overrides.
  Application/source changes select all localization tests and native UI tests,
  including French; locked Node installs provide both dictionaries in every
  job that runs CSpell.
  Documentation-test helpers under `tests/` select code; affected local docs checks
  remain required. Empty/unrelated changes select no suite; detection must still succeed.
- Keep `check` required in branch protection. Failed/cancelled detection or selected
  jobs, missing/unknown/inconsistent results block merge. Do not use workflow-level
  path skips that leave required statuses absent; see [job conditions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions).

## Required secret scanning

- Windows x64 Gitleaks 8.30.1, archive SHA-256 pinned in the workflow.
  Full-history checkout at the event/release SHA; `git --log-opts=--all` scans fetched refs.
- Generated config extends default rules; empty ignore file; inline allow comments
  disabled. Repository-local configuration/ignores cannot silently suppress findings.
- Full report/log redaction; report stays in `.tmp/gitleaks/`, never uploaded.
- Self-test: clean synthetic history passes; a deleted synthetic token fails despite
  an allow comment; report/output must redact it.
- Findings, scanner errors, failed self-tests, cancelled/skipped scans block `check`
  and therefore reusable release quality checks.
- Coverage excludes unreachable objects, uncommitted files, hosted issue/PR text
  and external assets. A passing scan does not prove the absence of secrets;
  [publication review](../../SECURITY.md#publication-boundary) remains required.

## Workflow validation

- Windows x64 actionlint 1.7.12, SHA-256 verified before extraction.
- `.github/workflows/`, `.github/scripts/`, `tests/ci/`, `tests/dependencies/` and
  Dependabot/label/release-rule changes select all-workflow validation;
  manual/full reusable runs always select it.
- Final gate requires success when selected, skipped when unselected; failed,
  cancelled, missing or unexpected results block merge/release quality.
- Checks workflow structure/expressions; ShellCheck/Pyflakes integrations disabled.
  Does not execute embedded PowerShell or prove hosted permissions/runtime behavior.
  Regression tests exercise the actual PowerShell merge gate/release command with mocks.

## Issue templates and additive PR labels

- [Bug](../../.github/ISSUE_TEMPLATE/bug_report.md)/[feature](../../.github/ISSUE_TEMPLATE/feature_request.md)
  templates assign `bug`/`enhancement`; [PR template](../../.github/pull_request_template.md)
  requests scope, actual local validation and review. Templates activate on `main`,
  without rewriting existing issues/PRs.
- [Label rules](../../.github/labeler.yml): `enhancement` for `feat/` head branches,
  `bug` for `fix/` head branches; type labels are additive with file labels.
  `documentation` covers Markdown and `docs/images/`,
  `dependencies` for manifests/locks/Dependabot, `ci` for workflows/CI scripts/tests
  or label/release-category rules. Priority/scientific review remains manual.
  Unclassified source changes receive no guessed type. Other existing issue
  labels remain manual.
- [Labeler workflow](../../.github/workflows/labeler.yml): trusted base configuration;
  `pull_request_target` opened/synchronize/reopened to `main`, including drafts/forks/Dependabot.
  No checkout, PR-code execution or custom secrets.
  Updated rules take effect after reaching `main`, on the next matching PR event.
- Permissions: `contents: read`, `pull-requests: write`; labels must exist.
  `sync-labels: false` preserves existing/manual labels. Labels neither approve nor merge.
  Validation stays read-only; label automation is independent of application runtime.

## Source release tags

[Release workflow](../../.github/workflows/source-release.yml): pushed `v*` tags
and authorized manual retries. Source/publication and Windows builds use Windows;
the reusable quality stage also builds and checks the native Linux/macOS artifacts.

| Stage             | Dependencies / result                                                                                                                                                                        |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `source`, 10 min  | Resolve/validate tag commit and release policy; check temporary source archive/recording integrity; build Python packages                                                                    |
| `quality`         | After source; call full reusable CI for that resolved commit                                                                                                                                 |
| `windows`, 30 min | After source/quality; locked build group, redistribution-input checks, standalone EXE and standard/complete ZIPs plus checksums; execute all three with isolated preferences/restricted PATH |
| `release`, 10 min | After successful source/quality/windows; verified publication; only job with `contents: write` and `actions: read`                                                                           |

- Failed/skipped/cancelled quality blocks Windows preparation/publication.
  This includes any missing or failed native package target. Publication downloads
  all six application artifacts and all four platform checksum files from the
  same run and verifies each inventory before uploading release assets.
  Missing provider sources are documented/reported; missing/modified catalog-listed
  archives fail verification.
- Temporary source archive is not uploaded; GitHub supplies source ZIP/tar.gz.
- GitHub generates categorized release changes from merged PRs using
  [release labels](../../.github/release.yml), preceded by a short reusable
  introduction. See [release notes policy](RELEASE.md#automatic-release-notes).
- No job creates tags or changes repository visibility.
  [Release guide](RELEASE.md) owns tag/version/ancestry policy, retries, artifact
  handling, download verification and documented redistribution limits.
- Hosted success does not replace local application/GUI or clean-Windows validation.

## Verification boundaries

- CI tests use `.tmp/` synthetic Git histories: cumulative changes, Unicode/spaces,
  renames/deletions, invalid revisions, output routing and actual PowerShell gate.
- Dependency tests cover templates, labels and permissions; actionlint covers workflow syntax.
- Local/static checks do not prove hosted labels, conditional execution or current
  branch protection. Fresh hosted evidence requires an authorized PR run and
  read-only settings inspection; record outcomes in PR metadata.

References: [issue templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository),
[Labeler](https://github.com/actions/labeler),
[PR target events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_target).
