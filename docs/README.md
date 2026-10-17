# Documentation index

[Project README](../README.md) covers capabilities and startup.
[AGENTS.md](../AGENTS.md) defines durable project rules.

## Scope, contracts and implementation

| Topic               | Authoritative documents                                                                                                                                                                                          |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Milestones          | [Roadmap](ROADMAP.md): M1/M2 and reduced M3 complete; M4 partial; M5–M8 planned                                                                                                                                  |
| Architecture        | [arc42 index](architecture/README.md): twelve maintained views; ADRs via chapter 09                                                                                                                              |
| Importer            | [DEV-REQ-002](requirements/DEV-REQ-002-forces-importer.md), [format observations](requirements/FORMAT-ANALYSIS.md), [plan](implementation/DEV-REQ-002/PLAN.md), [prompts](implementation/DEV-REQ-002/PROMPTS.md) |
| Scientific analysis | [DEV-REQ-003](requirements/DEV-REQ-003-scientific-analysis.md), [plan](implementation/DEV-REQ-003/PLAN.md), [prompts](implementation/DEV-REQ-003/PROMPTS.md); unresolved source semantics remain explicit        |

## Development and APIs

- [Windows setup](development/SETUP.md): installation/start scripts, required checks and VS Code.
- [Code quality](development/CODE_QUALITY.md), [documentation tests](development/DOCUMENTATION_TESTS.md),
  [CI routing](development/CI.md), [Dependabot policy](development/DEPENDABOT.md),
  [Codex configuration](development/CODEX.md).
- [Public importer](development/IMPORT_SERVICE.md), [canonical models](development/CANONICAL_MODELS.md),
  [decoder](development/STRICT_DECODING.md), [motion](development/MOTION_PARSING.md),
  [optional metadata/GPS](development/OPTIONAL_PARSING.md).
- [Analysis contracts and device primitives](development/ANALYSIS_MODELS.md).
- [Raw explorer plan](implementation/RAW_EXPLORER.md) and [Windows evidence](validation/RAW_EXPLORER.md):
  local file-to-chart workflow, focus workspace, controls and limitations.
- [Recording catalog](development/RECORDINGS.md): authorization, original filenames and fingerprints.

## Validation evidence

- [Reduced M3 acceptance](validation/M3.md): per-criterion evidence, extrema and focused Windows checks.

- [M1 acceptance](validation/M1.md) and [delivery status](validation/M1_DELIVERY.md).
- [M2 acceptance](validation/M2.md): criteria, traceability, Windows and hosted evidence.
- [M3 input/model/device evidence](validation/M3_STAGES.md) and [Stage 3](validation/M3_STAGE3.md): scoped API evidence; current reduced-M3 acceptance is defined in its plan.
- [Locked dependency inventory](validation/DEPENDENCIES.md), [Node security evidence](validation/DEPENDABOT.md),
  [developer-tool verification](validation/DEVELOPER_TOOLS.md).
- [Workspace scripts and documentation review](validation/WORKSPACE.md).

Requirements define contracts; plans define stage gates; API guides explain usage;
validation reports retain scoped commands/results and unresolved limits, without
implementation diaries. Architecture belongs exclusively in arc42.
Temporary logs/downloads belong in `.tmp/`.

[App-reference comparisons](validation/APP_REFERENCE.md) cover Manta, Kraken and
Voltron Nevera, with per-recording qualification and screenshot/numeric evidence.
It also includes GPS overview comparisons across all five originals and the
unconfirmed source-speed color hypothesis.
