# Workspace verification

<!-- cspell:words basetemp -->

[Windows setup](../development/SETUP.md) owns installation, startup and current
tool versions. The setup/start scripts were verified on native Windows x64,
Python 3.14.6 / uv 0.13.0 / Node 26.11.1, in the workspace-setup scope based on
`4b201c42adb8201882bc9c91483ca03124290a57`.

Recorded checks passed for locked development setup, isolated absent-environment
bootstrap, repeat setup, caller-directory restoration, missing-environment errors
and native start/close. A mismatched Node version is rejected before sync.
Start installs nothing and waits for window close.

This is script-level verification, not clean-OS/interpreter installation, ARM64,
manual editor interaction or release acceptance.
Current GUI checks belong in [explorer verification](RAW_EXPLORER.md).

## Documentation verification

The maintained documentation describes current behavior, acceptance boundaries,
API contracts, scientific limits and open work. Validation evidence is scoped;
application checks are not rerun for prose-only edits. Current review commands:

```text
npm run test:docs
```

Documentation-only scope: README and docs on `feat/4k-force-exports`, based on
d88304e25dc67b9c0cec6ffe9c55f03d4d74e66b. Native Windows Node 26.5.0:
Markdown/spelling passed and all 63 local-link cases passed
(`.tmp/docs-consolidation.log`). This is scoped tooling evidence, not pinned
Node 26.11.1 full-stack acceptance. No application code, fixtures or locks changed.

`python .tmp/check-doc-diagrams.py` verifies all nine retained Mermaid definitions
against the reviewed index: only one plain label changed and all control syntax
is identical (`.tmp/docs-diagrams.log`). No new parser/visual rendering, runtime,
hosted CI, external-link or scientific verification is claimed.

## Current delivery verification

Native Windows x64, Python 3.14.6 / Qt 6.12.0 / uv 0.13.0 /
Node 26.11.1 with locked dependencies. Scope: the complete export, batch,
localization, theme, reference-script and documentation changes on
`feat/4k-force-exports`, based on d88304e25dc67b9c0cec6ffe9c55f03d4d74e66b.

All [required checks](../development/SETUP.md#required-project-checks) passed:
lock consistency, Ruff lint/format, strict mypy/Pyright, type/dependency contracts,
CI routing and documentation. `uv run --locked pytest --basetemp=.tmp/delivery-pytest`
passed **1,441 cases** in 263.87 s. Documentation passes all 64 local-link cases,
Markdown and spelling. Native runner output is retained in
`.tmp/delivery-full-check.log` and `.tmp/delivery-final-check.log`; final
documentation receives its affected check before publication.
These are local results, not hosted CI or new full-recording export evidence.
