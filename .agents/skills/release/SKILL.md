---
name: release
description: Prepare and publish a Ride Forces Analyzer version using existing versioning, Windows checks, package builders and GitHub workflows, then verify the published downloads.
---

# Release

Use existing tools; do not create another release runner or duplicate project policy.
Read [AGENTS.md](../../../AGENTS.md), the [release guide](../../../docs/development/RELEASE.md)
and [required Windows checks](../../../docs/development/SETUP.md#required-project-checks).
Creating this skill or requesting preparation alone does not authorize publication.
Honor existing owner authorization; ask only for missing target version or permissions.

## 1. Prepare the version

- Confirm the target version and scope. Inspect branch, working tree, staged changes,
  existing tags/releases and related PRs; preserve unrelated owner changes.
- Use `uv run --locked python -m scripts.prepare_release` with the confirmed
  `--app-version` and/or independent `--plugin-version`; preview with `--dry-run`,
  then apply. It synchronizes product metadata and root/workspace lock entries.
  API targets require separate explicit owner approval. Omit targets without approval;
  never upgrade dependencies or protocol versions as a side effect.
- Update affected version assertions and user documentation. Do not blindly
  replace dependency versions or synthetic/historical test values.
- Check the independently versioned Stream Deck plugin as a separate deliverable.
  Follow its [version workflow](../../../plugins/stream-deck/README.md#independent-plugin-version)
  once for changed plugin code/data since the preceding release tag; keep that
  upcoming version across development commits. Do not bump again merely to prepare
  the release. An app release alone does not require a plugin bump.
  Preserve package/manifest/lock consistency and do not reuse the app version.
- GitHub generates the change list from merged PRs using
  [release categories](../../../.github/release.yml). Review user-readable PR titles
  and labels; do not maintain a second manual feature/change list.
- Keep the [release introduction](../../../docs/development/RELEASE_NOTES.md) short
  and reusable. Preserve its `{{VERSION}}`, `{{REPOSITORY}}` and `{{TAG}}`
  placeholders and preview their substitution. Add a concise Upgrade notes section
  only when this release needs specific user action; remove obsolete upgrade notes
  when preparing the next release. Follow version and redistribution policy.
- Version preparation runs three screenshot scripts in five sequential calls.
  Use [update-screenshots](../update-screenshots/SKILL.md) to review their outputs,
  captions and embedding. Reuse successful captures for unchanged inputs; do not
  rerun them as an additional preparation step. Fix failed generation and repeat
  the preparation command with the same targets to complete an interrupted refresh.

## 2. Validate locally

- Use native Windows; install locked release dependencies before validation with
  `uv sync --locked --all-extras --group dev --group build`.
  Run all required setup checks,
  including the full application suite, Node contracts/dependencies and documentation.
  Run `npm run test:stream-deck`; it builds the plugin, uses official offline packing
  and checks the archived runtime/licenses/profiles against the built bytes.
  Run the focused recording/service coverage gate from
  [code quality](../../../docs/development/CODE_QUALITY.md#recording-model-and-service-coverage).
  Run delivery-tool regressions only for affected inputs, as their skill requires.
- Inspect release/build/deployment scripts and validate workflows with the pinned
  actionlint installation/command in [CI](../../../.github/workflows/ci.yml).
  Existing packaging/CI tests cover script contracts; static checks do not prove a build.
- Development stays on Windows. Require the native Linux/macOS package jobs in
  [CI](../../../.github/workflows/posix-packages.yml) to pass for the release revision;
  do not attempt cross-compilation or treat Windows mocks as native acceptance.
- Fix release-scoped failures, rerun affected checks and rebuild affected packages.
  Reuse evidence only under AGENTS.md; do not weaken gates or expand the fix scope.

## 3. Build candidates and execute the local EXE

Use the same [Windows builder](../../../scripts/build_windows.py) as the GitHub
release pipeline, from the repository root in native Windows PowerShell:

```powershell
uv run --locked --group build python -m scripts.build_windows --release --work .tmp/release-preflight/windows
```

The shared builder creates the EXE, Standard ZIP and Complete ZIP with FFmpeg
together. Keep this single build path; do not split it or create an EXE-only runner.
Locally, smoke-test only the EXE; no additional ZIP extraction or ZIP smoke tests
are required.

Run the actual EXE with `--self-test` pointing to a fresh JSON report under `.tmp/`
and `--recording` pointing to the authorized Manta fixture. Reuse the isolation
rules from [the package checker](../../../scripts/check_windows_packages.py):
temporary preferences, no Python/Qt environment overrides and a System32-only
PATH. Wait for completion and require the expected version, successful GUI/import,
German/light presentation and 4K rendering in its report.

The GitHub pipeline also runs this builder and owns Python package builds and
checks of all three Windows artifacts, including the complete package's real CPU
encode. Do not run `scripts.check_windows_packages` locally as an additional
release-preparation gate; its ZIP checks belong to the pipeline.

Report the accepted redistribution scope and recorded verification limits accurately;
a successful EXE build does not establish clean-machine/signing acceptance. Keep logs and
outputs in `.tmp/`; no routine tracked validation diary.

Pack the already tested plugin with the existing workflow, without another build:

```powershell
npm run pack:built-plugin --workspace plugins/stream-deck
```

The archive is
`.tmp/stream-deck-package/Ride-Forces-Analyzer.streamDeckPlugin`.
An existing archive is protected; append `-- --force` only when intentionally replacing
that local candidate. The release CI retains it and `PLUGIN-SHA256SUMS.txt`, then the
publication job verifies and attaches both beside the application downloads.
Keep native archive-install, physical-device and macOS plugin acceptance explicit;
packing or mock SDK tests do not establish those results. Never replace user profiles
or unlink their development installation as an automatic release-preparation step.

## 4. Deliver the reviewed changes

Use [github-delivery](../github-delivery/SKILL.md) for authorized staging, grouped
commits, push, PR, green-check merge and local synchronization. Do not implement
replacement Git helpers. Local preparation/build checks precede publication.

After the final approved commit, validate its source archive before publishing a tag:

```powershell
git archive --format=zip --output=.tmp/release-preflight/source.zip HEAD
uv run --locked python .github/scripts/check-source-release.py .tmp/release-preflight/source.zip --tag vVERSION
```

Replace `vVERSION` with the confirmed target. Recheck the final merged release
revision against tested content; changed inputs require affected checks/builds again.

## 5. Publish and verify downloads

- Before merging a `release/<version>` PR, require authorization covering that merge,
  automatic tag creation and publication. Its version must already match
  `project.version`; merging it into `main` starts the existing release pipeline.
  Do not merge such a PR under merge-only authorization.
- For an explicitly authorized tag-triggered release, verify the
  release commit belongs to remote `main`, has its merged PR and green CI, and its
  version matches the new tag before tag creation/push and publication.
- Review the generated notes against the intended previous release before
  publication, using GitHub's generate-notes API with the target and previous tags.
  Confirm the categorized PR list, comparison link and introduction. Read-only
  preview does not authorize creating a tag or release; use the same previous tag
  for preview and publication if an explicit baseline is required.
- Observe `source → quality → windows → release` for that commit. Inspect failures;
  use the documented retry path only when appropriate. Never move a published tag,
  overwrite an existing release or blindly repeat an ambiguous remote mutation.
- Download the six published native packages, the `.streamDeckPlugin`, all four
  platform checksum files and `PLUGIN-SHA256SUMS.txt` with
  `gh release download` into a fresh directory under `.tmp/`. Verify release/tag
  identity, expected versioned asset names and every checksum. Smoke-test the
  downloaded standalone Windows EXE using the isolation and report checks above.
  Rely on the successful pipeline checks for Windows ZIPs, the Linux tarball and
  both macOS app ZIPs; do not repeat their extraction/execution checks on Windows.
  Native Linux/macOS execution requires the corresponding target OS. Locally built
  artifacts are not a substitute for downloaded-asset verification.
- Verify the downloaded plugin's checksum, independent manifest version, bundled
  runtime/licenses and Plus/Neo/Mobile profiles. Native installation/update requires
  actual Stream Deck execution; report it as open when unavailable. Do not claim
  Marketplace updates or macOS/hardware acceptance from a successful release upload.
- Stop on missing authorization, unavailable required validation or unresolved
  failures/ambiguous publication; report the concrete blocker and actual remote state.
- Report version/tag/commit, PR/release links, actual local/build/hosted results,
  download hashes/execution results and remaining limits. Claim completion only
  when the requested publication and download verification have passed.
