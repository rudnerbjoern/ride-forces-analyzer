# Documentation index

[Project README](../README.md) covers startup and use.
[Roadmap](ROADMAP.md) is the authority for milestone status.
[AGENTS.md](../AGENTS.md) defines durable collaboration rules.

## Product contracts

| Topic             | Contract                                                                                                                                                         | Verification                                                              |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Importer          | [Requirements](requirements/DEV-REQ-002-forces-importer.md), [scope](implementation/DEV-REQ-002/PLAN.md), [format observations](requirements/FORMAT-ANALYSIS.md) | [M2](validation/M2.md)                                                    |
| Analysis          | [Requirements](requirements/DEV-REQ-003-scientific-analysis.md), [scope](implementation/DEV-REQ-003/PLAN.md)                                                     | [M3](validation/M3.md), [source comparisons](validation/APP_REFERENCE.md) |
| Explorer / GPS    | [Explorer contract](implementation/RAW_EXPLORER.md)                                                                                                              | [Explorer](validation/RAW_EXPLORER.md)                                    |
| Video export      | [Formats, profiles and previews](implementation/VIDEO_EXPORT.md)                                                                                                 | [Video / editor compatibility](validation/VIDEO_EXPORT.md)                |
| Presets / batches | [SQLite and queue contracts](implementation/EXPORT_BATCHES.md)                                                                                                   | [Persistence / queue](validation/EXPORT_BATCHES.md)                       |
| Localization      | [English/German presentation](development/LOCALIZATION.md)                                                                                                       | [Text / layout](validation/LOCALIZATION.md)                               |

## Development

The [Manta export layout reference](EXPORT_THEMES.md) compares all five profiles
at the same strong G-force peak, with complete placement and enlarged details.

- [Windows setup](development/SETUP.md): installation, startup and canonical checks.
- [Code quality](development/CODE_QUALITY.md), [documentation checks](development/DOCUMENTATION_TESTS.md),
  [CI routing](development/CI.md), [dependency updates](development/DEPENDABOT.md),
  [Codex configuration](development/CODEX.md).
- Import APIs: [service](development/IMPORT_SERVICE.md),
  [models](development/CANONICAL_MODELS.md), [decoder](development/STRICT_DECODING.md),
  [motion](development/MOTION_PARSING.md), [metadata/GPS](development/OPTIONAL_PARSING.md).
- [Analysis APIs](development/ANALYSIS_MODELS.md).
- [Export layout API](development/EXPORT_LAYOUTS.md): per-layout modules,
  renderer contract and explicit plugin registration.
- [Recording catalog](development/RECORDINGS.md): authorization, filenames and hashes.
- [Dependency inventory](validation/DEPENDENCIES.md) and
  [dated security boundary](validation/DEPENDABOT.md).
- [Foundation acceptance](validation/M1.md), [workspace verification](validation/WORKSPACE.md)
  and [developer-tool verification](validation/DEVELOPER_TOOLS.md).

## Documentation ownership

Architecture lives exclusively in the [twelve arc42 chapters](architecture/README.md);
chapter 09 links ADR rationale. Requirements define acceptance, contracts/API guides
define behavior, and validation pages retain concise scope/results/limits.
Scientific comparisons and recording permissions are evidence, not development logs.
Temporary runner output belongs in `.tmp/`; implementation diaries and completed
execution prompts are not maintained.
