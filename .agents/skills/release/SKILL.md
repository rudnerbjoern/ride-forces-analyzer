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
- Update `project.version` in `pyproject.toml` and refresh the root project entry
  with `uv lock`. Review the lock diff; do not upgrade unrelated dependencies.
- Update affected version assertions and user documentation. Do not blindly
  replace dependency versions or synthetic/historical test values.
- GitHub generates the change list from merged PRs using
  [release categories](../../../.github/release.yml). Review user-readable PR titles
  and labels; do not maintain a second manual feature/change list.
- Keep the [release introduction](../../../docs/development/RELEASE_NOTES.md) short
  and reusable. Preserve its `{{VERSION}}`, `{{REPOSITORY}}` and `{{TAG}}`
  placeholders and preview their substitution. Add a concise Upgrade notes section
  only when this release needs specific user action; remove obsolete upgrade notes
  when preparing the next release. Follow prerelease and redistribution policy.
- Refresh screenshots affected by visible/version changes through
  [update-screenshots](../update-screenshots/SKILL.md); do not introduce a new capture tool.

## 2. Validate locally

- Use native Windows; install locked release dependencies before validation with
  `uv sync --locked --all-extras --group dev --group build`.
  Run all required setup checks,
  including the full application suite, Node contracts/dependencies and documentation.
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

Report manifest-listed redistribution gaps accurately; a successful EXE build
does not close them or establish clean-machine/signing acceptance. Keep logs and
outputs in `.tmp/`; no routine tracked validation diary.

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

- Only with authorization covering tag creation/push and publication: verify the
  release commit belongs to remote `main`, has its merged PR and green CI, and its
  version matches the new tag. Follow the existing tag-triggered release workflow.
- Review the generated notes against the intended previous release before
  publication, using GitHub's generate-notes API with the target and previous tags.
  Confirm the categorized PR list, comparison link and introduction. Read-only
  preview does not authorize creating a tag or release; use the same previous tag
  for preview and publication if an explicit baseline is required.
- Observe `source → quality → windows → release` for that commit. Inspect failures;
  use the documented retry path only when appropriate. Never move a published tag,
  overwrite an existing release or blindly repeat an ambiguous remote mutation.
- Download the six published native packages and four platform checksum files with
  `gh release download` into a fresh directory under `.tmp/`. Verify release/tag
  identity, expected versioned asset names and every checksum. Smoke-test the
  downloaded standalone Windows EXE using the isolation and report checks above.
  Rely on the successful pipeline checks for Windows ZIPs, the Linux tarball and
  both macOS app ZIPs; do not repeat their extraction/execution checks on Windows.
  Native Linux/macOS execution requires the corresponding target OS. Locally built
  artifacts are not a substitute for downloaded-asset verification.
- Stop on missing authorization, unavailable required validation or unresolved
  failures/ambiguous publication; report the concrete blocker and actual remote state.
- Report version/tag/commit, PR/release links, actual local/build/hosted results,
  download hashes/execution results and remaining limits. Claim completion only
  when the requested publication and download verification have passed.
