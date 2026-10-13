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

M2 Stage 1 canonical models and diagnostics are implemented for synthetic inputs.
Stage 3 motion validation operates on source envelopes; Stage 2 now provides
strict source decoding and resource guards. See [Stage 2 evidence](validation/M2_STAGE2.md)
and [Stage 3 evidence](validation/M2_STAGE3.md).
File importing and the M3–M8 product features below remain **planned**. Each
additional implementation stage requires a new owner instruction.

## M2 — Ride Forces importer

Parse `.forces` JSON defensively; preserve unknown metadata and bytes; convert numeric strings;
validate sample rate, sequence lengths, indices and GPS sentinels. **Exit:** lossless ingest of
all five [current fixtures](development/RECORDINGS.md) with regression tests.
[Stage 1](validation/M2_STAGE1.md) implements immutable representations;
[Stage 3](validation/M2_STAGE3.md) validates available motion, vectors and indices.
The [strict decoder](validation/M2_STAGE2.md) is implemented; optional-data parsing
and full importer integration remain planned;
M2 acceptance is not complete.

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
