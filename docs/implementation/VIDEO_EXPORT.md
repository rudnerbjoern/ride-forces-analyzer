# Ride overlay video export

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

<!-- cspell:words qscale Bahnschrift -->

## Supported output

| Setting            | Contract                                                                                                   |
| ------------------ | ---------------------------------------------------------------------------------------------------------- |
| Output             | One video per recording; transparent ProRes 4444 MOV (default) or independent opaque H.264 MP4             |
| Canvas             | HUD: native 1920×1080 / 1080×1920; other profiles: 3840×2160 / 2160×3840                                   |
| Profiles           | Flow Ribbon (assistant opening default), Corner Instruments, HUD, G-Orbit, four-panel column               |
| Frame-rate choices | 24/25/30/50/59.94/60 fps; default 50 without a valid saved preference                                      |
| Context window     | 1–60 s, default 12; shared source position and centered cursor in time plots                               |
| Alignment          | Manual in DaVinci Resolve; source-video ingestion/synchronization excluded                                 |

[Manta G-Orbit demo](https://youtu.be/tsRzD416voU): exported overlay over Onride footage.

## Contracts

### Defaults, destinations and saved settings

- Settings → Export persists the default frame rate in `preferences.sqlite3`.
  Save changes it; Cancel and temporary assistant edits do not. Presets/batches
  retain their own rates, including exact `60000/1001`.
- The local `render_jobs` preference defaults to 1 and accepts positive integers,
  capped at the detected logical processor count (1 if unavailable). Settings →
  Export applies it to newly started individual and batch exports. It is not part
  of visual presets or saved batch snapshots.
- Save dialog suggests the source recording stem, ` - `, the selected layout's
  displayed name and `.mov`/`.mp4` (for example, `Manta - HUD.mov`).
  Successful exports remember the destination folder across restarts, separately
  from the recording folder. Missing folders use dialog defaults; cancellation or
  failure preserves the previous folder.
- Presets/immutable batch jobs explicitly retain aspect, overlay language, vertical
  direction and analysis recipe; incomplete saved settings are rejected.
  Mixed-aspect batches are supported.
- Overlay language is English/German/French, initially following UI language but independently
  selectable. Production previews/frames share localized labels/numbers.
  Replay clocks, source values, geometry, signs and units remain unchanged.
  German and French glyph bounds are checked in every profile/aspect. Known layout names
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
- Orientation is independent of force smoothing. Layout, aspect, position, language, video
  rate and seeking do not recalculate analysis. Running exports/preview workers
  retain bound snapshots independently of later workspace changes.
  This includes custom Gravity/Incline references and subsequent resets: all five
  preview layouts and the encoder consume the same effective basis and tilt.
  Original source directions remain available as evidence; see
  [reference calibration](../development/ANALYSIS_MODELS.md#reference-calibration).
- Source time is index/rate; fractional output positions interpolate adjacent values.
  Inclusive ranges include the final sample interval; duration rounds up to a frame.
- 59.94 uses exact `60000/1001` in timing, frame counts, FFmpeg and saved settings.
  Use a matching 59.94 editing timeline for GoPro footage recorded at that rate.
- Default interval uses effective start/end markers; current selection and entire
  recording are alternatives. Plot context outside the exported interval is blank.
- Replay labels retain sample-counter notation. Graphics omit Hz/fps; neither
  identifies the POV video's rate. Technical rates remain in settings/metadata/encoding.

### Geometry, directions and colors

- All profiles fit the full canvas. Portrait Ribbon stacks force cards;
  Corners, G-Orbit and Column preserve complete instruments with proportional
  scaling/margins. Previews retain aspect without cropping/stretching.
  Frame composition and encoder padding share region geometry.
- The export API accepts a layout/format-supported position or uses that format's
  default. Coordinates and dimensions come from the layout; frame composition,
  large previews, thumbnails and encoder padding use the same selected region.
  The assistant offers localized positions beside Layout profile. Layout/format
  changes retain a supported selection or choose an equivalent edge/corner on the
  same side, falling back to the default. Thumbnails use the same policy.
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

### HUD

- Frameless full-screen arrangement with a transparent center: vertical force and
  provisional airtime context at the left, acceleration/braking at the right,
  and signed lateral force below. A transparent-to-black gradient gently darkens
  the bottom histories; the center remains transparent. No reticle is drawn.
- Fine major/minor ticks, luminous pointers, bold technical-font readouts, colored
  bloom and soft black shadows remain transparent over footage. Bahnschrift is used
  when installed, using its Bold weight for values; the existing scalable font
  fallback applies otherwise. Prepared airtime labels are shown in uppercase.
- A narrow orientation line sits at the outer right edge, alongside the existing
  instrument height, with 0° at the top and 180° at the bottom. Only 0°, 45°, 90°,
  135° and 180° are marked and labeled. A white triangular bug follows the prepared
  orientation, including fractional-sample interpolation. Missing orientation hides
  the entire line, labels and bug for that frame; no placeholder is shown.
- The vertical instrument has independent negative/positive bounds in both formats:
  Seated starts at −1.5…+5 g and Flying at −4…+3 g. The recording's effective
  `riding_position` selects Flying only for the explicit `Flying` value; absent
  source metadata already defaults to Seated in the importer. Other or unavailable
  positions use the general Seated display range without changing source metadata.
  Each bound expands outward independently in 0.5 g steps to include actual valid
  samples in the export interval. Both sides use equal pixels per g; zero moves
  with the bounds instead of staying at the center. Direction reversal mirrors
  the instrument without negating values or exchanging its numeric bounds.
  Only whole g values are labeled. Whole, half and quarter g values use long,
  medium and short tick marks respectively; wider ranges reduce tick density
  with an integer stride while preserving the exact endpoint marks.
- Lateral and longitudinal instruments retain symmetric scales. Four minor ticks
  separate major labels. Lateral uses at least ±2 g in both formats,
  expanding to the next 0.5 g boundary from the largest absolute actual selected
  peak (for example, 2.05 g → ±2.5 g), independently of major tick spacing.
  Longitudinal uses
  ±1.5 g in both formats. Before frame generation, its actual valid selected
  samples determine the largest absolute peak: only peaks exceeding 1.5 g expand
  that scale outward. Padded chart bounds and samples outside the export interval
  do not affect instrument ranges. All ranges remain fixed for the
  entire export. Major tick
  spacing grows for wider ranges to retain readable density; values are never clipped.
- Three thin, wide force histories share a centered time cursor aligned exactly
  with the lateral instrument's zero. Their left/right time spans have equal width
  around that line; baselines and time ticks use the same plot bounds. They use the
  selected interval's independent per-channel scales. Each is symmetric around
  zero, includes 5% headroom and rounds outward to 0.1 g (minimum ±0.1 g).
  These ranges use valid selected samples, stay fixed during the entire export
  and do not change the large instrument scales. Curve heights therefore show
  variation within each channel, rather than equal g-per-pixel across channels.
  Histories use the
  selected time window. Selecting HUD in the assistant sets a 30-second window
  (15 seconds before/after the cursor), still editable; loaded presets retain their
  saved window. Time advances left-to-right; vertical respects its inversion,
  lateral is positive-up, and longitudinal acceleration is above zero/braking below.
  Curves break at missing samples and omit context outside the export interval.
  Longitudinal segments change green/red exactly at their zero crossing.
- Independent markers disappear for missing channels. Readouts use existing
  interpolation and prepared context; no speed, gears or vehicle attitude is invented.
- Bright bars along all three instrument scales show independent positive/negative
  held peaks: 1.5 seconds, then release toward zero at 1 g/s, as in G-Orbit.
  Larger peaks replace the held value immediately. Pointers, lateral dot and
  numeric readouts continue to show current values. Envelopes start at the first
  selected sample, reset at missing samples and use source time, independent of
  seek order and video rate. Missing current values hide their bars and pointers.
- The only position is `full_screen` in both formats. Native 1920×1080/1080×1920
  drawing is exported directly without resizing, for scaling in the video editor.
  Both transparent and opaque output retain these dimensions, including saved
  presets and batches. Preview galleries keep their common display dimensions.
  Static effects are prepared once; moving effects use instrument/history tiles.
  Rendering is independent of seek order and previous frames.
- Removed layout keys are unsupported in saved presets/jobs; no automatic remapping
  or database cleanup is performed.

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
- `rendering.parallel.render_region_bytes` uses the direct serial path for one
  job. Multiple jobs use a bounded thread pool with independent renderers, images
  and fonts per worker, sharing only the immutable timeline. Results reach the
  encoder in frame order, with at most the job count plus one outstanding frames.
  Closing on cancellation or failure cancels queued work and joins active renders.
  Batch videos remain sequential; their frames use the selected render-job count.
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
