# Workspace setup validation

The Windows workspace supplies `setup.ps1` and `start.ps1`.
[Setup guide](../development/SETUP.md) is authoritative for current versions,
locked installation, checks and editor settings. Current application startup/layout
is covered in [explorer validation](RAW_EXPLORER.md).

## Verified script behavior

Native Windows x64 / Python 3.14.6 / uv 0.13.0 / Node 26.11.1, on
`chore/workspace-setup-and-docs`, base `4b201c42adb8201882bc9c91483ca03124290a57`.
Script scope: setup/start and workspace documentation; `.tmp/workspace-checks.log`
and temporary runners retain actual output.

| Native command / scenario                                                           | Result                                                                                                     |
| ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .tmp/run-setup.ps1`        | Development setup completed with locked Python/Node dependencies                                           |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .tmp/test-clean-setup.ps1` | Isolated absent environment created; uv bootstrap and Python selection passed                              |
| `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .tmp/test-workspace.ps1`   | Parse, missing-environment error, repeat setup, caller-directory restoration and native start/close passed |
| Development setup with mismatched Node 26.5.0                                       | Rejected before dependency synchronization                                                                 |

Start performs no installation and waits for the window to close. Setup can use
installed Python/cached wheels; initial missing downloads require network.
Clean OS/interpreter installation, ARM64 and manual VS Code interactions are not
verified by these checks. Original recordings are never installation inputs.
Runtime/API/quality results are scoped in the relevant acceptance reports; no
claim of a fresh security or scientific audit is made here.

## Documentation consistency

The documentation describes current behavior, implemented/planned boundaries and
known limits. Validation retains compact revision/platform/command/result scope;
it is not an implementation diary. Roadmap entries agree with importer, analysis,
explorer and GPS modules. ADR rationale, scientific references/discrepancies,
requirements and recording authorization/digests remain retained.

Documentation-only scope (2026-10-17): README, roadmap/index, affected architecture,
analysis/importer plans/ADRs and validation summaries, including owner-approved
reduced M3 scope and explicit deferred/excluded work. No source, tests, fixtures,
locks or check configuration changed. Native Windows `npm run test:docs` and
`.tmp/node-v26.11.1-win-x64/node.exe .tmp/stage3-mermaid.mjs` verify Markdown,
spelling, local links and arc42 diagram syntax; results are recorded in
`.tmp/explorer-docs.log` and `.tmp/docs-mermaid.log`. Application test evidence is
reused for unchanged executable inputs. Mermaid visual/hosted rendering and a
fresh security/release audit are outside this review.

Results: Markdown lint passed for 62 documents, spelling for 138 files, all 62
local-link tests passed, and all nine arc42 Mermaid definitions parsed.
`git diff --check` passed. These checks cover documentation consistency/syntax;
they do not claim new application or hosted acceptance.
