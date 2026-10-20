# Roadmap

Milestone status refers to the implemented/remaining scope below, not every
possible feature. [README](../README.md) explains current use;
[architecture](architecture/README.md) owns subsystem design.

| Milestone                  | Status                  | Implemented / remaining scope                                                                                                                                                         |
| :------------------------- | :---------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| M1 — Foundation            | Complete                | Windows setup/start, strict settings, Qt bootstrap, tooling and CI; [bootstrap contract](architecture/06_runtime_view.md#qt-bootstrap)                                                |
| M2 — Importer              | Complete                | Lossless offline import, metadata/weather, attributes, GPS and diagnostics; [import contract](architecture/08_concepts.md#source-ownership-and-validation)                            |
| M3 — Analysis              | Complete, reduced scope | Immutable models, explicit device/frame APIs, source-app projection/mean and selected-range extrema; [analysis contract](architecture/08_concepts.md#scientific-provenance-and-gates) |
| M4 — Explorer              | Partial                 | Raw/calibrated charts, markers, time zoom, selection, extrema, GPS, light/dark and English/German UI; persistent ride library and full acceptance remain                              |
| M5 — Playback              | Planned                 | Deterministic clock, pause, seek, speed and interpolation                                                                                                                             |
| M6 — Exports               | Partial                 | Five 4K layouts, portrait/landscape, transparent/opaque video, previews, SQLite presets/batches and optional NVIDIA encoding; CSV/JSON/PNG sequence and full acceptance remain        |
| M7 — Video synchronization | Planned                 | Local video ingest, offsets, timeline preview and frame-accurate alignment                                                                                                            |
| M8 — Windows release       | Partial                 | Portable EXE, standard/complete ZIPs and tag release pipeline; redistribution sources/notices, signing and clean-Windows verification remain                                          |

## Product boundaries

Calibrated display is available for any usable import; failures retain raw data.
Source-bound Manta confirmation does not qualify arbitrary recordings or all
smoothing windows. Kraken's start mismatch and Voltron's maximum-display difference
remain in [source comparisons](validation/APP_REFERENCE.md).

GPS supplies coarse spatial context only. Universal physical rider calibration,
additional filter families, qualified event semantics, broad statistics and analysis
benchmark research are deferred. Separately configured provisional airtime episodes
follow the [event contract](implementation/AIRTIME_EVENTS.md); they do not establish
physical qualification. They are not reduced-M3 blockers.
Installed libraries do not establish implemented features.

SQLite stores export configuration, not the planned ride library. Exports use
manual Onride alignment; interactive playback and synchronization are separate.

## Next product work

1. Finish M4's persistent library and remaining explorer acceptance.
2. Complete M6 beyond the [video](implementation/VIDEO_EXPORT.md) and
   [batch](implementation/EXPORT_BATCHES.md) contracts.
3. Scope M5, M7 and M8 independently.

Validation scope follows the owner's current instructions. A roadmap entry grants
no implementation or Git-operation authorization.
