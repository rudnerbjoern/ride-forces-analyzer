# M1 delivery plan — 2026-10-13

## Reviewed scope

Deliver the Windows Python 3.14.6 foundation, validated startup settings,
fixture/GUI/tooling regression tests, locked dependencies, editor configuration,
PR-only CI and aligned documentation. No M2 importer or analysis is included.
The original Manta recording remains byte-identical. Temporary logs, downloads,
environments and build artifacts are excluded; only `.tmp/.gitkeep` is delivered.

## Branch strategy

One working branch, `milestone/m1-foundation`, contains the related M1 changes.
Separate parallel branches would split shared lock files and tool configuration
without providing independent deliverables. The owner authorized renaming the
existing GitHub default branch `master` to `main`; its original commit remains
unchanged. Create the working branch from that unchanged base after local checks.
Never commit on or push to `main`.

## Commit groups

1. Python foundation: `.python-version`, `pyproject.toml`, `uv.lock`, startup settings
   and entry point, runtime/GUI/Ruff/fixture tests, including dimension-boundary regression.
2. Development tooling: text conventions, ignore rules, `.tmp/.gitkeep`, Node manifests
   and lockfile, documentation/type-contract tests, VS Code and Codex configuration.
3. CI: the PR-only Windows workflow for Python quality and documentation checks.
4. Documentation: README, AGENTS, GitHub instructions, roadmap, architecture, ADR,
   development guides, dependency audit and M1 validation/delivery evidence.

Use exact path lists, inspect each staged group and follow the
[commit-message rules](../../.github/commit-message-instructions.md). Do not stage
ignored artifacts or include additional recordings. Pure working-tree line-ending
noise that produces no staged diff is not a separate change.

## Publication and acceptance

Complete locked installation, native Windows quality/GUI tests, documentation
checks, adapter discovery/execution, package build and fixture-integrity checks
before creating the working branch and commits. Push only the explicit working
branch destination, then create one draft pull request with base `main`.

Because CI triggers only on pull requests, hosted verification follows draft-PR
creation. Inspect both jobs and their actual steps on the PR revision. Fix any
failure on the same working branch and push the correction to the same PR.
After successful hosted verification, commit the evidence and update the milestone
status, then verify CI on that final revision. Keep the PR a draft; do not merge it.

M1 is complete only when every [roadmap](../ROADMAP.md) acceptance criterion is
verified. Unverified criteria stay open in [M1 validation](M1.md), even if local
checks passed. Draft status and PR merge are review/delivery states, not evidence
of a successful CI run.
