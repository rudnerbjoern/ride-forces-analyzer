# 4K ride overlay export

For instructions on creating an overlay and using it in a video editor, see the
[user guide](../user/VIDEO_EXPORT.md). This page defines the technical contracts.

Windows uses the existing optional bundled encoder. Linux/macOS select an external
native `ffmpeg` from PATH or the Browse action; frame generation and encoding remain
separate. Export staging stays beside the chosen output and is cleaned on success,
cancellation or failure, including when the application launches from a read-only
directory. Frozen Linux library paths are removed from external encoder processes.
See [native deployment requirements](../development/RELEASE.md#linux-and-macos-packages).

Current output/interaction contracts. Architecture owns
[component/API boundaries](../architecture/05_building_block_view.md#video-export-boundary),
[runtime](../architecture/06_runtime_view.md#4k-export-runtime),
[snapshot reuse/lifetime](../architecture/08_concepts.md#snapshot-lifetime-and-reuse)
and [encoder qualification limits](../architecture/07_deployment_view.md#encoder-installation).
The [layout API](../development/EXPORT_LAYOUTS.md) owns styling/extensions;
the [roadmap](../ROADMAP.md) owns planned scope.

<!-- cspell:words qscale -->

## Supported output

| Setting            | Contract                                                                                                   |
| ------------------ | ---------------------------------------------------------------------------------------------------------- |
| Output             | One video per recording; transparent ProRes 4444 MOV (default) or independent opaque H.264 MP4             |
| Canvas             | Landscape 16:9, 3840×2160; portrait 9:16, 2160×3840                                                        |
| Profiles           | Flow Ribbon (assistant opening default), Corner Instruments, Telemetry Capsule, G-Orbit, four-panel column |
| Frame-rate choices | 24/25/30/50/59.94/60 fps; default 50 without a valid saved preference                                      |
| Context window     | 1–60 s, default 12; shared source position and centered cursor in time plots                               |
| Alignment          | Manual in DaVinci Resolve; source-video ingestion/synchronization excluded                                 |

[Manta G-Orbit demo](https://youtu.be/tsRzD416voU): exported overlay over Onride footage.

## Contracts

### Defaults, destinations and saved settings

- Settings → Export persists the default frame rate in `preferences.sqlite3`.
  Save changes it; Cancel and temporary assistant edits do not. Presets/batches
  retain their own rates, including exact `60000/1001`.
- Save dialog suggests the source `.forces` stem plus `.mov`/`.mp4`.
  Successful exports remember the destination folder across restarts, separately
  from the recording folder. Missing folders use dialog defaults; cancellation or
  failure preserves the previous folder.
- Presets/immutable batch jobs explicitly retain aspect, overlay language, vertical
  direction and analysis recipe; incomplete saved settings are rejected.
  Mixed-aspect batches are supported.
- Overlay language is English/German, initially following UI language but independently
  selectable. Production previews/frames share localized labels/numbers.
  Replay clocks, source values, geometry, signs and units remain unchanged.
  German glyph bounds are checked in every profile/aspect. Known layout names
  translate; Flow Ribbon and G-Orbit retain their identities.

### Assistant and previews

| Interaction            | Contract                                                                                                                      |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Opening                | Two-step modal assistant binds current analysis, graph cursor and smoothing; does not follow workspace changes                |
| Preview sample         | All five thumbnails and large preview use production RGBA at the exact source sample, independent of video-frame quantization |
| Refresh                | Settings/background changes use a debounced worker; only latest revision applies                                              |
| Background             | Checkerboard/light/dark are preview-only; preview needs neither FFmpeg nor encoding                                           |
| Out-of-interval cursor | Retained unchanged; explicit full-recording-context warning                                                                   |
| Review                 | Actual interval/settings; destination selection and full rendering require final Export video action                          |
| Navigation             | Scrollable content, pinned navigation/export actions for smaller/high-DPI desktops and translated settings                    |
| Close/Escape           | Preserve source sample while open; respect active-encoding cancellation                                                       |

### Analysis and time mapping

- Preparation reuses an identical source/configuration snapshot; otherwise
  `prepare_export_analysis` reuses matching upstream stages and rebuilds affected ones.
  Complete available history precedes interval selection.
- `prepare_export`/`build_previews` accept `RecordingAnalysis`, settings and concrete
  source indices; layouts consume a bound `ExportTimeline`.
  Force/orientation views share prepared buffers; context uses full-history labels
  without per-layout reclassification.
- Orientation is independent of force smoothing. Layout, aspect, language, video
  rate and seeking do not recalculate analysis. Running exports/preview workers
  retain bound snapshots independently of later workspace changes.
- Source time is index/rate; fractional output positions interpolate adjacent values.
  Inclusive ranges include the final sample interval; duration rounds up to a frame.
- 59.94 uses exact `60000/1001` in timing, frame counts, FFmpeg and saved settings.
  Use a matching 59.94 editing timeline for GoPro footage recorded at that rate.
- Default interval uses effective start/end markers; current selection and entire
  recording are alternatives. Plot context outside the exported interval is blank.
- Replay labels retain sample-counter notation. Graphics omit Hz/fps; neither
  identifies the POV video's rate. Technical rates remain in settings/metadata/encoding.

### Geometry, directions and colors

- All profiles fit the full canvas. Portrait Ribbon/Capsule stack force cards;
  Corners, G-Orbit and Column preserve complete instruments with proportional
  scaling/margins. Previews retain aspect without cropping/stretching.
  Frame composition and encoder padding share region geometry.
- Compact time plots show three forces plus numeric tilt; Column adds an
  orientation plot. Export uses calibrated channels at the selected centered-mean
  setting. Bounds use selected extrema plus 5% outward padding and −1/0/+1 g labels.
- Compact panels are translucent with transparent surroundings/rounded corners;
  data are opaque: cyan vertical, yellow lateral, green/red longitudinal.
  Text/curves are outlined; opaque output composites over black.
  Exact geometry/styles belong to [design constants](../development/EXPORT_LAYOUTS.md#design-constants).

| Channel/axis              | Contract                                                                                                                                                                         |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Vertical                  | Default positive-down (seat pressure), negative-up (lifting); manually reversible in every layout, persisted explicitly                                                          |
| Time                      | Horizontal left-to-right; vertical bottom-to-top: left/bottom past, right/top future                                                                                             |
| Column                    | Horizontal time axes throughout; lateral positive-down by default                                                                                                                |
| Compact lateral histories | Vertical time axis advances upward; negative/left forces left of zero, positive/right forces right                                                                               |
| Current-only lateral      | Horizontal left/right; G-Orbit upper semicircle centered at top                                                                                                                  |
| Lateral scale             | Equal scale in both directions using larger absolute selected bound; fixed direction across compact layouts/aspects/previews                                                     |
| Lateral inversion         | Explicit setting affects Column only; disabled in assistant                                                                                                                      |
| Longitudinal              | Positive acceleration above zero; negative braking below zero in histories/current-only instruments, all layouts/aspects; not invertible                                         |
| Numeric signs             | Axis inversion never negates source values or changes right/left/braking signs                                                                                                   |
| Orientation               | Angle between normalized current source gravity and stored vertical, clipped cosine, 0–180°; not yaw/GPS heading; missing/zero gravity breaks curve, no force-derived substitute |

### G-Orbit

- Independent signed concentric force arcs: vertical left, longitudinal right,
  lateral upper inner semicircle. Vertical zero is at the left equator, signed
  extremes bottom/top; numeric values sit inside arcs.
- Separate right orientation semicircle: measured-angle marker at 0° top, 90° right,
  180° bottom. No stretching/reconstructed attitude; missing tilt has no marker.
- No replay footer. Square region with circular translucent background and fully
  transparent corners; portrait scales all dimensions proportionally.
- Bold scale numbers; white current-value bars with dark outlines cross tracks.
  Translucent fills composite over tracks; opaque current arcs/white markers stay on top.
- Positive/negative peaks held independently for 1.5 source-time seconds, then
  released toward zero at 1 g/s without falling below current magnitude.
  Reaching held value restarts hold; larger peaks replace it immediately.
- Envelopes start at prepared interval's first sample and reset on gaps.
  Immutable source-time envelopes give identical random-access preview/frame
  behavior independently of query order/fps.
- Peak bars use dark outlines and muted channel colors; longitudinal green/red by sign.

### Estimates and progress

| Estimate             | Contract and limits                                                                                                                      |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| File size            | Live approximate MiB range in settings/review, using rounded frame count, canvas/overlay area and codec; no FFmpeg or trial rendering    |
| Size uncertainty     | Uncalibrated planning heuristic, not measured bitrate/guaranteed bounds; motion, detail, filtering and CPU/GPU encoding can exceed range |
| Remaining frame time | Single-video export, 2 s timer; elapsed monotonic time per submitted frame × pending count; min:sec, including startup overhead          |
| ETA states           | Estimating before first frame; finalization after last frame has no predicted duration; cancel/failure/completion clears ETA             |

### Encoding and FFmpeg

- Background export provides progress/cancellation; window close requests cancel.
  Pillow RGBA generation remains separate from external FFmpeg encoding.
- Probe actual NVIDIA Vulkan ProRes with alpha / NVENC H.264; otherwise CPU fallback.
  Display selected backend. GPU ProRes never receives CPU `qscale`.
- Pipe only the selected layout region; encoder pads remaining transparent/opaque
  canvas to selected dimensions.
- Never overwrite existing files. Publish completed output exclusively; use
  same-volume hard links to avoid duplicate large files. Cross-volume or unsupported
  links fall back to exclusive copying; failed/cancelled copies remove partial output.
- Processing stays offline after installation, reusing Pillow. External full FFmpeg
  build/version/checksum is pinned in `ffmpeg.json`; `setup.ps1 -VideoExport` installs it.
  The assistant also accepts an installed executable.
- FFmpeg Browse opens the configured executable's folder, including relative paths
  or missing executables. A directory input opens itself; empty uses native defaults.
  Cancel retains path; choosing a file replaces it.
- Recording bytes, metadata, GPS and source values remain unchanged.
