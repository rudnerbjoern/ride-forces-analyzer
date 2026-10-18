# Roadmap

Milestone status refers to the scope defined by its requirements, not every
possible feature. [README](../README.md) explains current use;
[architecture](architecture/README.md) owns subsystem design.

| Milestone                  | Status                  | Implemented / remaining scope                                                                                                                                                  |
| -------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| M1 — Foundation            | Complete                | Windows setup/start, strict settings, Qt bootstrap, tooling and CI; [acceptance](validation/M1.md)                                                                             |
| M2 — Importer              | Complete                | Lossless offline import, metadata/weather, attributes, GPS and diagnostics; [acceptance](validation/M2.md)                                                                     |
| M3 — Analysis              | Complete, reduced scope | Immutable models, explicit device/frame APIs, source-app projection/mean and selected-range extrema; [acceptance](validation/M3.md)                                            |
| M4 — Explorer              | Partial                 | Raw/calibrated charts, markers, time zoom, selection, extrema, GPS, light/dark and English/German UI; persistent ride library and full acceptance remain                       |
| M5 — Playback              | Planned                 | Deterministic clock, pause, seek, speed and interpolation                                                                                                                      |
| M6 — Exports               | Partial                 | Five 4K layouts, portrait/landscape, transparent/opaque video, previews, SQLite presets/batches and optional NVIDIA encoding; CSV/JSON/PNG sequence and full acceptance remain |
| M7 — Video synchronization | Planned                 | Local video ingest, offsets, timeline preview and frame-accurate alignment                                                                                                     |
| M8 — Windows release       | Planned                 | Standalone package, install/uninstall, diagnostics and clean-Windows verification                                                                                              |

## Product boundaries

Calibrated display is available for any usable import; failures retain raw data.
Source-bound Manta confirmation does not qualify arbitrary recordings or all
smoothing windows. Kraken's start mismatch and Voltron's maximum-display difference
remain in [source comparisons](validation/APP_REFERENCE.md).

GPS supplies coarse spatial context only. Universal physical rider calibration,
additional filter families, automatic events, threshold durations, broad statistics
and analysis benchmark research are deferred. They are not reduced-M3 blockers.
Installed libraries do not establish implemented features.

SQLite stores export configuration, not the planned ride library. Exports use
manual Onride alignment; interactive playback and synchronization are separate.

## Next product work

1. Finish M4's persistent library and remaining explorer acceptance.
2. Complete M6 beyond the [video](implementation/VIDEO_EXPORT.md) and
   [batch](implementation/EXPORT_BATCHES.md) contracts.
3. Scope M5, M7 and M8 independently.

Only focused tests are currently authorized; full suites need renewed owner
approval. A roadmap entry grants no implementation or Git-operation authorization.
