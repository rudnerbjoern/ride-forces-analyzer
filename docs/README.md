# Documentation

[Project README](../README.md) explains the application and startup.
The analyzer processes `.forces` recordings made with the external
[Ride Forces app](https://rideforces.com/) for iPhone or Apple Watch.
This is an independent project, with no affiliation with, endorsement from or
sponsorship by that app or its developer.
[Roadmap](ROADMAP.md) distinguishes implemented scope from open work.
[Architecture](architecture/README.md) describes the system in twelve arc42 chapters;
chapter 9 retains decision status and rationale. Completed requirements, stage plans and
historical acceptance reports are not maintained.

## Current product and API contracts

- [Explorer and GPS](implementation/RAW_EXPLORER.md).
- [Video export](implementation/VIDEO_EXPORT.md), [saved presets and batches](implementation/EXPORT_BATCHES.md).
- [All export themes](EXPORT_THEMES.md), [layout extension API](development/EXPORT_LAYOUTS.md).
- [English/German presentation](development/LOCALIZATION.md).
- Import APIs: [service](development/IMPORT_SERVICE.md), [models](development/CANONICAL_MODELS.md),
  [decoder](development/STRICT_DECODING.md), [motion](development/MOTION_PARSING.md),
  [metadata/GPS](development/OPTIONAL_PARSING.md).
- [Analysis APIs](development/ANALYSIS_MODELS.md), [scientific source comparisons](validation/APP_REFERENCE.md).

## Development and publication

- [Windows setup and checks](development/SETUP.md), [contributions](../CONTRIBUTING.md),
  [agent rules](../AGENTS.md), [private security reports](../SECURITY.md).
- [Code quality](development/CODE_QUALITY.md), [documentation checks](development/DOCUMENTATION_TESTS.md),
  [CI routing](development/CI.md), [dependency updates](development/DEPENDABOT.md),
  [Codex settings](development/CODEX.md).
- [Dependency inventory](validation/DEPENDENCIES.md),
  [third-party licenses](../THIRD_PARTY_NOTICES.md).
- [First public release preparation](development/RELEASE.md).
- [Desktop, export and Windows-package validation](validation/WINDOWS_PACKAGES.md).
- [Recording catalog and authorization](development/RECORDINGS.md),
  [recording reuse license](../tests/fixtures/real/README.md), [image reuse license](images/README.md).

## Ownership

Keep current behavior, planned work and known limits distinct. Architecture owns
the system overview; API guides own detailed interfaces and product contracts own
interaction/output rules. Preserve necessary scientific observations, decision
rationale, security findings and recording permissions. Temporary runner evidence
belongs in `.tmp/`; do not turn documentation into development chronicles.
