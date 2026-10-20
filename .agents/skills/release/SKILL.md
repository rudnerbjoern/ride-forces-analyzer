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
- Update affected version assertions, user documentation and
  [release text](../../../docs/development/RELEASE_NOTES.md). Keep its `{{VERSION}}`,
  `{{REPOSITORY}}` and `{{TAG}}` placeholders; preview their substitution for the target.
  Do not blindly replace dependency versions or synthetic/historical test values.
- Describe shipped behavior and known limits, not internal test history. Follow
  current prerelease classification and redistribution policy in the release guide.
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
- Fix release-scoped failures, rerun affected checks and rebuild affected packages.
  Reuse evidence only under AGENTS.md; do not weaken gates or expand the fix scope.

## 3. Build and execute the actual packages

Run from the repository root in Windows PowerShell:

```powershell
uv build --out-dir .tmp/release-preflight/python
uv run --locked --group build python -m scripts.build_windows --release --work .tmp/release-preflight/windows
uv run --locked --group build python -m scripts.check_windows_packages .tmp/release-preflight/windows/assets --recording (Get-ChildItem tests/fixtures/real/Manta-*.forces | Select-Object -First 1).FullName
```

Require actual EXE, standard ZIP and complete ZIP checks to pass, including GUI/import,
rendering and the complete package's real CPU encode. Check versions, filenames,
checksums and collected notices. Report manifest-listed redistribution gaps accurately;
a successful build does not close them or establish clean-machine/signing acceptance.
Keep logs and outputs in `.tmp/`; no routine tracked validation diary.

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
- Observe `source → quality → windows → release` for that commit. Inspect failures;
  use the documented retry path only when appropriate. Never move a published tag,
  overwrite an existing release or blindly repeat an ambiguous remote mutation.
- Download the three published Windows assets and `WINDOWS-SHA256SUMS.txt` with
  `gh release download` into a fresh directory under `.tmp/`. Verify release/tag
  identity and expected versioned asset names, then run `scripts.check_windows_packages`
  against those downloaded files with the same native Windows command as above.
  Locally built artifacts are not a substitute for downloaded-asset verification.
- Stop on missing authorization, unavailable required validation or unresolved
  failures/ambiguous publication; report the concrete blocker and actual remote state.
- Report version/tag/commit, PR/release links, actual local/build/hosted results,
  download hashes/execution results and remaining limits. Claim completion only
  when the requested publication and downloaded-package checks have passed.
