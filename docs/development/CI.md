# Pull-request CI selection

Architecture owns [local/hosted acceptance boundaries](../architecture/07_deployment_view.md#validation-and-release-boundary).
This guide defines workflow routing and gates; [setup](SETUP.md) owns local commands.

Development checks remain on Windows. The reusable
[native package workflow](../../.github/workflows/posix-packages.yml) additionally
builds and executes Linux x64 and macOS arm64/x64 packages on their own runners.
`posix` runs only for manual full CI and release calls; PRs skip native package
jobs. The final `check` gate requires every selected target to succeed.
Jobs have readable display names; the final check-run name remains `check` for
branch protection and the delivery helper. Technical job IDs and selection outputs
remain stable.

Compatible jobs share dependency caches. uv separates `dev` and `build` dependency
sets; setup-uv's keys also distinguish platform, architecture, Python version and
locked inputs. npm jobs use the same download-cache path and keys containing OS,
architecture, Node-version input and lockfile hash. Restore prefixes stay within
that platform/architecture/Node version; setup-node's additional automatic npm
cache is disabled. Jobs restore independent local copies; test environments and
results remain separate. Concurrent cold jobs may miss the same cache; an existing
entry is immutable. GitHub's branch/PR access restrictions still apply.
Gitleaks/actionlint cache only their pinned download archives and always verify
the SHA-256 before extraction. Test reports, recordings and user data are never
cached. Jobs without dependency/tool installation need no dependency cache.
Each target has a 30-minute budget, uses locked dependencies, tests native platform
contracts and executes the extracted frozen app with a real CPU encode. Linux uses
Xvfb; macOS verifies app signatures. Manual CI builds and verifies packages without
uploading them. Only release calls enable `upload-packages`; verified
packages and their checksum files are then retained for 14 days for publication.
They contain neither recordings nor user databases.
These jobs qualify target packages; they do not add a Linux/macOS developer setup.

| Control                  | Contract                                                                                                                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Validation workflow      | [ci.yml](../../.github/workflows/ci.yml): read-only, Windows development checks and native Linux/macOS packages; PRs targeting `main`, manual dispatch, reusable release calls |
| Full runs                | Manual dispatch selects all suites; release calls validate the resolved commit, with verified application/UI evidence reuse as described below                                 |
| Mandatory scan           | Independent Gitleaks job on every validation run                                                                                                                               |
| Checkout                 | Event `github.sha` or supplied release `revision`; release jobs use the same validated tag commit                                                                              |
| Concurrency              | New PR pushes cancel older runs for that workflow/PR; manual runs have independent groups                                                                                      |
| Main pushes              | No duplicate validation run                                                                                                                                                    |
| Dependency resolution    | Locked Python commands throughout                                                                                                                                              |
| Scanner/linter downloads | Three retries for all transfer errors; 30 s connection / 120 s per attempt; TLS certificate/revocation and SHA-256 checks mandatory; exhausted retries fail                    |
| Time limits              | Non-UI application 15 min; UI/skills/actionlint/Gitleaks 10 min; detection/docs/plugin/final gate 5 min                                                                        |

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
the merge gate.

Release calls can reuse the application and UI jobs from the latest CI run for
the associated merged PR. The release-policy helper requires a green run and final
gate, successful application/UI jobs, identical PR/release Git trees and each job's
logged tested tree. Both Windows runner image versions must match the release
runner, and the release workflow revision must equal the tag commit. Git-tree
identity includes source, tests, workflows, tool-version pins and dependency locks.
The release log identifies the reused PR, run and commit. Missing logs, API failures,
changed content/images/workflows or skipped/failed jobs select fresh application/UI
checks. PRs and ordinary manual full CI never reuse results.

Only these two expensive jobs are skipped after verified reuse. Secret scanning,
dependency/workflow/docs/skill/plugin/interoperability checks, native package builds
and runtime checks still execute. The final gate requires reused jobs to be skipped
and every remaining selected job to succeed.

| Job                       | Selection / result                                                                                                                                                                                                    |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gitleaks`                | Every run; checksum-pinned scanner self-test and complete fetched-history scan                                                                                                                                        |
| `dependency-check`        | Every run detects changes and tests the selector; selected `dependencies` additionally installs locked Node dependencies and runs `npm run test:dependencies`                                                         |
| `actionlint`              | Workflow/script/CI-test/dependency-test and Dependabot/label/release-rule changes; manual/full reusable runs; validate all workflows                                                                                  |
| `documentation`           | Any Markdown path, including source/tests/skills and deletions/renames; locked Node install and `npm run test:docs`                                                                                                   |
| `code`                    | Non-Markdown application/source/test/script and shared Python/Node/Git/editor inputs, excluding CI metadata and Node/PowerShell contracts; lint/format/types and pytest excluding UI and Stream Deck interoperability |
| `ui`                      | Same selection as `code`; complete `tests/ui` serially on a separate Windows runner                                                                                                                                   |
| `stream-deck`             | Affected plugin/shared Node/CI inputs; manual/full and release runs always; locked Node install, strict TypeScript build and `npm run test:stream-deck`                                                               |
| `stream-deck-integration` | Transport/protocol, plugin implementation, shared toolchain/CI inputs or interoperability tests; independent Python/Qt and Node runner for `tests/integration/stream_deck`                                            |
| `posix`                   | Manual full CI and release calls only; native Linux x64/macOS arm64/x64 build and runtime checks; skipped for all PR changes                                                                                          |
| `skills`                  | Non-Markdown skill implementation/tests, consumed commit policy, Python manifest/lock/version and Git/editor settings; separate skill Ruff/mypy/pytest                                                                |
| `check`                   | Always evaluate detection, contract-selection validity and selected job results: selected = success, unselected = skipped                                                                                             |

The `code`, `ui` and `stream-deck-integration` jobs run disjoint test directories;
no test runs twice in these jobs. Application tests explicitly exclude UI and
`tests/integration/stream_deck`. UI tests remain serial per desktop and are required
with application code, including manual/release runs. The independent integration
job is selected for changes to either transport/protocol implementation or shared
inputs, and always for full/manual/release runs. Its selected result is mandatory
in `check`; failed, cancelled, missing or unexpectedly skipped execution blocks it.
UI tests and application screenshots need no Node/plugin build. Plugin-specific
profile/illustration tests live under `plugins/stream-deck/tests` and run only in
the plugin suite; its runner supplies locked Python/Qt and Node dependencies and
full release history. Shared wire examples live in `tests/fixtures/stream_deck_protocol.json`;
each domain validates its own implementation against them.
A second Windows setup can reduce wall-clock waiting when runners are available;
it does not guarantee lower total runner minutes.

- Markdown-only, plugin-only and skill-only changes skip application tests. CI metadata,
  Node/PowerShell workflow contracts and selector changes select dependency/syntax
  checks without application/UI/skill tests, including CI/native package workflow
  changes. Python release-helper changes retain conservative application validation;
  shared toolchain/manifest inputs also select application and skill checks.
  Mixed changes select the union of affected suites.
- Plugin selection covers non-Markdown files under `plugins/stream-deck/`, root
  package manifests/lock, Node version and VS Code test settings, plus the CI/release
  workflows, selector and selector tests. Plugin-only changes select no Python/UI
  suites. Failed, cancelled or missing selected plugin results block `check`;
  releases reuse full CI and always require the plugin job.
- Shared Qt/Node transport, control contracts and interoperability fixtures select both
  application and plugin checks.
  `tests/integration/stream_deck/test_transport.py` is the explicit cross-domain
  check: it runs the real application Qt server with the real TypeScript client,
  including authentication and restart/reconnect. It runs only in the independent
  `stream-deck-integration` job with both toolchains; it needs no plugin build or npm
  packages because the client uses native Node APIs. The pure server tests remain
  under `tests/support`. Run it locally with
  `uv run --locked pytest tests/integration/stream_deck`.
- Plugin tests build the self-contained local artifact, validate it with the official
  offline CLI and exercise SDK/app WebSocket hosts; they need no installed device software.
  Release calls additionally pack the tested folder without rebuilding and retain
  the `.streamDeckPlugin` and `PLUGIN-SHA256SUMS.txt` for verified publication.
- Commit-policy Markdown selects docs/skills. Code-only/skill-only/plugin-only runs supply
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
- Plugin builds verify package/manifest/lock consistency and compare changed inputs
  with the preceding reachable release tag. Development commits reuse one upcoming
  version; a changed plugin must exceed its version at that release. Full history
  and tags prevent docs-only follow-ups or a newly tagged HEAD from hiding a missed increase.
  See [plugin versioning](../../plugins/stream-deck/README.md#independent-plugin-version).

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
- [Label rules](../../.github/labeler.yml): `enhancement` for `feat/` or `feature/` head branches,
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
  all six application artifacts, the Stream Deck plugin and all five checksum files from the
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
