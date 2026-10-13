# Roadmap

## M1 — Project foundation
- [x] Create `src` layout, separated subsystems, executable minimal Qt window, metadata, docs, test infrastructure, CI definition and fixture.
- [ ] Verify environment bootstrapping and GUI launch on **Windows**.
- [ ] Verify GitHub Actions checks after repository creation.
**Exit criteria:** Windows install and startup; Ruff, mypy and pytest pass; CI passes; design docs committed.

## M2 — Ride Forces importer
Parse `.forces` JSON defensively; preserve unknown metadata and bytes; convert numeric strings; validate sample rate, sequence lengths, indices and GPS sentinels. **Exit:** lossless ingest of Manta fixture with regression tests.

## M3 — G-force analysis
Use documented calibration vectors, transform into rider coordinates, validate sign conventions, compare reference UI statistics, implement configurable smoothing. **Exit:** tested, repeatable computations with deviation report.

## M4 — Explorer GUI
Ride library, 3-axis charts, scrubber, zoom, segment selection, statistics. **Exit:** complete fixture browsable without blocking UI.

## M5 — Playback
Realtime marker, speed adjustment, pause, seek and sample interpolation. **Exit:** deterministic playback timeline.

## M6 — Exports
CSV, JSON, PNG, standalone MP4, alpha-ready overlay and PNG image sequence; profile-based layouts. **Exit:** visual sync and transparency verified in DaVinci Resolve.

## M7 — Video synchronization
Video ingest, offsets, timeline preview, frame-accurate matching and export. **Exit:** reproducible sync of a user-supplied POV recording.

## M8 — Windows release
Standalone packaging, diagnostics, install/uninstall, regression suite and documentation. **Exit:** app installed on a clean Windows VM and verified.

Complete milestones sequentially. Record decisions in `docs/decisions/`.
