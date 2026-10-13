# Roadmap

## M1 — Project foundation

- [x] Create `src` layout, separated subsystems, executable minimal Qt window, metadata, docs, test
      infrastructure, CI definition and fixture.
- [x] Verify environment bootstrapping and native Qt GUI launch on **Windows**, Python 3.14.6.
- [x] Verify GitHub Actions checks after repository creation (initial Python 3.13 commit).
- [x] Verify local Ruff lint/format, mypy, Pyright, type contracts, pytest and documentation checks.
- [x] Verify original Manta fixture bytes against the initial Git blob and regression digest.
- [x] Verify both GitHub Actions jobs for the updated Python 3.14.6 configuration and tests.
- [x] Commit the reviewed design documentation on the authorized M1 branch.

**Status:** Complete on 2026-10-13; see [verified acceptance evidence](validation/M1.md).
[PR #1](https://github.com/rudnerbjoern/ride-forces-analyzer/pull/1) was merged with
owner authorization. The later [four-recording expansion](development/RECORDINGS.md)
has separate verification notes in the M1 report.
**Exit criteria:** Windows install and native GUI startup; all checks in the
[development guide](development/SETUP.md) pass; both PR CI jobs pass on the updated
revision; reviewed design documentation committed. Delivery uses a branch and draft PR
targeting `main`; merge remains a separate owner decision.

The callable M2 importer is implemented; GUI importing and M3–M8 remain planned.
Each additional implementation stage requires a new owner instruction.

## M2 — Ride Forces importer

The read-only Path/bytes service imports schema 2.2.0 into immutable recordings,
preserving original bytes, metadata, ordered attributes and independent GPS data.
**Status:** Local AC-01–09 verified; AC-10 (dedicated PR and hosted CI) remains open.
See [M2 validation](validation/M2.md) and the [public API](development/IMPORT_SERVICE.md).
**Exit:** All five [fixtures](development/RECORDINGS.md) import losslessly and every
acceptance criterion passes. M2 is not complete until hosted CI is verified.

## M3 — G-force analysis

Use documented calibration vectors, transform into rider coordinates, validate sign conventions,
compare reference UI statistics, implement configurable smoothing. **Exit:** tested, repeatable
computations with deviation report.

## M4 — Explorer GUI

Ride library, 3-axis charts, scrubber, zoom, segment selection, statistics. **Exit:** all five complete
fixtures can be browsed without blocking UI.

## M5 — Playback

Realtime marker, speed adjustment, pause, seek and sample interpolation. **Exit:** deterministic
playback timeline.

## M6 — Exports

CSV, JSON, PNG, standalone MP4, alpha-ready overlay and PNG image sequence; profile-based layouts.
**Exit:** visual sync and transparency verified in DaVinci Resolve.

## M7 — Video synchronization

Video ingest, offsets, timeline preview, frame-accurate matching and export. **Exit:** reproducible
sync of a user-supplied POV recording.

## M8 — Windows release

Standalone packaging, diagnostics, install/uninstall, regression suite and documentation. **Exit:**
app installed on a clean Windows VM and verified.

Complete milestones sequentially. Record decisions in `docs/decisions/`.
