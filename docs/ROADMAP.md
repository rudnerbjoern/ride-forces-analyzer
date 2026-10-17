# Roadmap

Status describes the current implementation; partial functionality does not close
an entire milestone. [README](../README.md) covers use, [architecture](architecture/README.md)
covers subsystem boundaries, and validation reports retain scoped evidence.

| Milestone                  | Status   | Implemented                                                                                                                                   | Remaining acceptance                                                                                                         |
| -------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| M1 — Foundation            | Complete | Windows setup/start, typed settings, Qt bootstrap, quality tooling and CI                                                                     | None within M1; [evidence](validation/M1.md)                                                                                 |
| M2 — Importer              | Complete | Lossless offline Path/bytes import, metadata/weather, ordered attributes, independent GPS and diagnostics                                     | Additional schemas require explicit contracts; [evidence](validation/M2.md)                                                  |
| M3 — Analysis              | Complete | Immutable analysis models, explicit units/device vectors, provisional frames, source-app projection/mean and selected-range extrema           | None within reduced M3; [focused acceptance](validation/M3.md)                                                               |
| M4 — Explorer              | Partial  | Background loading, raw/calibrated charts, sample navigation, time zoom/reset, selection, markers, metadata, GPS overview and focus workspace | Persistent ride library and full M4 acceptance                                                                               |
| M5 — Playback              | Planned  | —                                                                                                                                             | Deterministic playback clock, pause, seek, speed control and interpolation                                                   |
| M6 — Exports               | Planned  | —                                                                                                                                             | CSV/JSON/PNG, opaque MP4, transparent overlay/PNG sequence, layout profiles and Resolve verification                         |
| M7 — Video synchronization | Planned  | —                                                                                                                                             | Local video ingest, offsets, timeline preview and frame-accurate matching/export                                             |
| M8 — Windows release       | Planned  | —                                                                                                                                             | Standalone package, diagnostics, install/uninstall and clean-Windows validation                                              |

## Implemented analysis and explorer

Calibrated forces defaults on for any import with usable source directions;
preparation errors retain raw channels with a diagnostic. Centered smoothing is
configurable from 1–51 odd samples, default 11, with live updates and right-click
reset. Lateral signs mean right/left; longitudinal signs mean acceleration/braking.
The Manta reference has source-bound owner confirmation at its compared default
window. Other files remain individually provisional despite feature availability.
[Source-app evidence](validation/APP_REFERENCE.md) records the known Kraken start
mismatch and Voltron vertical-maximum display difference.

The explorer supports bounded time zoom, marker-based default/reset, replay sample
notation, fixed force bounds and -1/0/+1 g reference labels. GPS supplies coarse
offline spatial context independently of force analysis. The dark focus workspace
groups chart controls, current values and inspector settings; technical details
are expandable. See [explorer contracts](implementation/RAW_EXPLORER.md) and
[Windows validation](validation/RAW_EXPLORER.md).

## Open work

1. Complete M4's persistent library and remaining explorer acceptance.
2. Implement M5–M8 with their own acceptance gates.

Reduced M3 is complete: selected-range min/max values are shown in the inspector
with source sample, recording/replay time and processing context. All current
AC-01–AC-10 have [focused native Windows evidence](validation/M3.md).
The owner-authorized pre-delivery full check passed 1,060 application tests.
Further full suites remain on hold until another explicit release.

Additional filters, event detection, threshold durations, broad statistics,
universal physical sensor/rider calibration and analysis benchmark research are
deferred, not M3 completion requirements. GPS geodesics/speed analysis is outside
the current product scope; GPS remains coarse spatial context. No GeographicLib
adoption is required. Playback interpolation is scoped with M5 if needed.

Installed packages do not establish planned capabilities. GPS remains a spatial reference; the app-reference display makes no universal
physical calibration claim. Excluded research is not a blocker for reduced M3.
Each new stage and every Git delivery operation require the applicable authorization
in [AGENTS.md](../AGENTS.md). No additional implementation is implied by this roadmap.
