# Roadmap

Current milestone scope, not a development history or a list of all possible
features. [README](../README.md) owns usage; [architecture](architecture/README.md)
owns system design and scientific boundaries.

| Milestone                  | Status   | Implemented / remaining scope                                                                                                                                                           |
| -------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1 — Foundation            | Complete | Windows setup/start, strict settings, Qt bootstrap, tooling/CI; [bootstrap](architecture/06_runtime_view.md#qt-bootstrap)                                                               |
| M2 — Importer              | Complete | Lossless offline import, metadata/weather, attributes, GPS/diagnostics; [import contract](architecture/08_concepts.md#source-ownership-and-validation)                                  |
| M3 — Analysis              | Complete | Immutable models, device/frame APIs, source-app projection/mean, extrema, shared snapshots/service and provisional context/events; [analysis contracts](development/ANALYSIS_MODELS.md) |
| M4 — Explorer              | Complete | Raw/calibrated charts, markers, time zoom, selection/extrema, GPS, appearance themes and EN/DE/FR UI                                                                                    |
| M5 — Playback              | Complete | Sample playback at 0.5×/1×/2×, pause/resume and seeking                                                                                                                                 |
| M6 — Exports               | Complete | Five layouts (native HD HUD, otherwise 4K), both aspects, transparent/opaque video, previews, presets/batches, CSV/JSON, optional NVIDIA                                                |
| M7 — Video synchronization | Planned  | Local video ingest, offsets, timeline preview, frame-accurate alignment                                                                                                                 |
| M8 — Windows release       | Partial  | Portable EXE, standard/complete ZIPs, notice collection and tag pipeline; owner-confirmed clean-Windows EXE launch; redistribution material and installer/uninstaller remain            |
| M9 — Linux / macOS         | Partial  | Native Linux x64/macOS arm64/x64 packages and mandatory runtime CI; clean-machine qualification remains open                                                                            |

## Product boundaries

- [Display/scientific policy](architecture/08_concepts.md#scientific-provenance-and-gates):
  usable imports support calibrated display with raw fallback. Manta's scoped
  confirmation does not qualify arbitrary recordings/windows;
  [source comparisons](validation/APP_REFERENCE.md) retain Kraken/Voltron discrepancies.
- GPS remains coarse spatial context. Universal rider calibration, additional
  filter families, qualified event semantics, broad statistics and analysis
  benchmark research are deferred. [Provisional airtime episodes](implementation/AIRTIME_EVENTS.md)
  use project-defined rules; scientific validation of these categories is not an
  M3 completion requirement. They do not establish physical qualification.
- Installed libraries do not establish features. SQLite stores export configuration;
  manual Onride alignment is separate from playback/synchronization.
- [Release obligations](development/RELEASE.md#windows-packages) identify missing
  redistribution sources/notices and the limits of workstation package checks.
- Paid code signing and macOS notarization are outside release scope;
  see [distribution constraints](architecture/02_architecture_constraints.md#distribution-constraints).

## Next product work

- Scope M7 and remaining M8 work independently.

Validation follows owner instructions. Roadmap entries authorize neither
implementation nor Git operations.
