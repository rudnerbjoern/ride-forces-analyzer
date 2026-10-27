# Documentation

[Project README](../README.md) explains the application and startup.
The analyzer processes `.forces` recordings made with the external
[Ride Forces app](https://rideforces.com/) for iPhone or Apple Watch.
This is an independent project, with no affiliation with, endorsement from or
sponsorship by that app or its developer.
[Roadmap](ROADMAP.md) distinguishes implemented scope from open work.
[Architecture](architecture/README.md) describes the system in twelve arc42 chapters;
chapter 9 retains decision status and rationale.

## For users

- [Windows, Linux and macOS installation](user/INSTALLATION.md):
  downloads, checksums, first launch, FFmpeg, updates, privacy and startup problems.
- [Explore a recording](user/EXPLORER.md): navigate, zoom, select intervals,
  inspect extrema, adjust smoothing, change appearance and open GPS.
- [Choose your appearance](user/APPEARANCE.md): compare themes, try them out
  and save your favorite.
- [Understand forces and airtime](user/FORCES_AND_AIRTIME.md): signs, colors,
  context labels and interpretation limits.
- [Export a ride overlay](user/VIDEO_EXPORT.md): choose a range and layout,
  preview, save a video and place it above your footage.
- [Export sample data as CSV](user/CSV_EXPORT.md): save a selected interval for
  spreadsheets or other analysis tools.
- [Export sample data as JSON](user/JSON_EXPORT.md): app-shaped arrays with
  additional analysis data, or structured Analyzer JSON with shared time/quality.
- [Choose an export layout](user/EXPORT_LAYOUTS.md): compare placement, read the
  instruments and check landscape/portrait previews.
- [Presets and batches](user/EXPORT_BATCHES.md): reuse settings, queue recordings
  and find results or handle failed jobs.

## Current product and API contracts

- [Explorer and GPS](implementation/RAW_EXPLORER.md).
- [Video export contract](implementation/VIDEO_EXPORT.md), [saved presets and batches](implementation/EXPORT_BATCHES.md).
- [CSV sample export contract](implementation/CSV_EXPORT.md).
- [JSON sample export contract](implementation/JSON_EXPORT.md).
- [All export themes](EXPORT_THEMES.md), [layout extension API](development/EXPORT_LAYOUTS.md),
  [Manta demo with all five overlays](https://youtu.be/0sGiE6F8YlI) and
  [additional Manta HUD demo](https://youtu.be/JGcNPKoKU1Q).
- [Provisional airtime context](implementation/AIRTIME.md) and
  [separate opt-in airtime events](implementation/AIRTIME_EVENTS.md).
- [Current screenshots, reference settings and image license](images/README.md).
- [Localization: English, German and French](development/LOCALIZATION.md).
- Import APIs: [service](development/IMPORT_SERVICE.md), [models](development/CANONICAL_MODELS.md),
  [decoder](development/STRICT_DECODING.md), [motion](development/MOTION_PARSING.md),
  [metadata/GPS](development/OPTIONAL_PARSING.md).
- [Scientific source comparisons](validation/APP_REFERENCE.md).
- [Editable calibration markers](development/ANALYSIS_MODELS.md#reference-calibration):
  source-evidenced Gravity/Incline calibration, persistence and partial recalculation.

## Unified analysis

- [Unified recording analysis API](development/ANALYSIS_MODELS.md#unified-recording-analysis):
  immutable snapshots, shared stages, sample views and the class diagram.
- [Analysis runtime](architecture/06_runtime_view.md#explorer-analysis-delivery):
  service subscriptions, worker/UI delivery and the notification sequence.

## Development and publication

- [Windows setup and checks](development/SETUP.md), [contributions](../CONTRIBUTING.md),
  [agent rules](../AGENTS.md), [private security reports](../SECURITY.md).
- [Code and documentation quality](development/CODE_QUALITY.md),
  [CI routing](development/CI.md),
  [Codex settings](development/CODEX.md).
- [Dependencies and update policy](development/DEPENDENCIES.md),
  [third-party licenses](../THIRD_PARTY_NOTICES.md).
- [Release policy and native packages](development/RELEASE.md).
- [Recording catalog and authorization](development/RECORDINGS.md),
  [recording reuse license](../tests/fixtures/real/README.md), [image reuse license](images/README.md).

## Planned work

- [Full-frame and bounded overlay export](requirements/BOUNDED_OVERLAY_EXPORT.md).

## Ownership

Keep current behavior, planned work and known limits distinct. Architecture owns
the system overview; API guides own detailed interfaces and product contracts own
interaction/output rules. Preserve necessary scientific observations, decision
rationale, security findings and recording permissions. Temporary runner evidence
belongs in `.tmp/`; do not turn documentation into development chronicles.
