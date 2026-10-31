# Ride overlay video export

<!-- cspell:words libx -->

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
[runtime](../architecture/06_runtime_view.md#video-export-runtime),
[snapshot reuse/lifetime](../architecture/08_concepts.md#snapshot-lifetime-and-reuse)
and [encoder qualification limits](../architecture/07_deployment_view.md#encoder-installation).
The [layout API](../development/EXPORT_LAYOUTS.md) owns styling/extensions;
the [roadmap](../ROADMAP.md) owns planned scope.

<!-- cspell:words qscale Bahnschrift -->

## Supported output

| Setting            | Contract                                                                                       |
| ------------------ | ---------------------------------------------------------------------------------------------- |
| Output             | One video per recording; transparent ProRes 4444 MOV (default) or independent opaque H.264 MP4 |
| Full-frame canvas  | HUD: native 1920×1080 / 1080×1920; other profiles: 3840×2160 / 2160×3840                       |
| Export area        | Full frame (default) or complete native Content area; HUD supports Full frame only             |
| Profiles           | Flow Ribbon (assistant opening default), Corner Instruments, HUD, G-Orbit, four-panel column   |
| Frame-rate choices | 23.976/24/25/30/50/59.94/60 fps; default 50 without a valid saved preference                   |
| Context window     | 1–60 s, default 12; shared source position and centered cursor in time plots                   |
| Alignment          | Manual in DaVinci Resolve; source-video ingestion/synchronization excluded                     |

[Manta overlay demo](https://youtu.be/0sGiE6F8YlI): all five layouts in turn over Onride footage.
The additional [Manta HUD demo](https://youtu.be/JGcNPKoKU1Q) shows HUD using
the supplied [Manta reference recording](../development/RECORDINGS.md#manta).

## Contracts

Four-panel column is landscape-only: a 960×2160 rectangle fills the complete height
of its 3840×2160 Full-frame canvas. Unsupported format/layout combinations are
unavailable in the selector and preview gallery; other layouts support both formats.

### Defaults, destinations and saved settings

- Settings → Export persists the default frame rate in `preferences.sqlite3`.
  Save changes it; Cancel and temporary assistant edits do not. Presets/batches
  retain their own rates, including exact `24000/1001` and `60000/1001`.
- `rendering.model.StandardFrameRate` owns standard rate values, display labels and
  exact fractions. `EXPORT_FRAME_RATES` follows enum order; `DEFAULT_FRAME_RATE`
  selects 50 fps. `FrameRate` also permits custom integers from 1 to 120.
  Standard integers normalize to enum members in `ExportSettings`; Python callers
  use enum members for fractional rates. Preset JSON and encoder metadata retain
  integer whole rates and exact fractional strings, without a storage migration.
- The local `render_jobs` preference defaults to 1 and accepts positive integers,
  capped at the detected logical processor count (1 if unavailable). Settings →
  Export applies it to newly started individual and batch exports. It is not part
  of visual presets or saved batch snapshots.
- Save dialog suggests the source recording stem, ` - `, the selected layout's
  displayed name and `.mov`/`.mp4` (for example, `Manta - HUD.mov`).
  Successful exports remember the destination folder across restarts, separately
  from the recording folder. Missing folders use dialog defaults; cancellation or
  failure preserves the previous folder.
- Presets/immutable batch jobs retain aspect, export area, position, overlay language,
  vertical direction and analysis recipe. Omitted optional fields use declared defaults,
  including Full frame for `extent`; invalid supplied or missing required values fail.
  Mixed-aspect and mixed-area batches are supported.
- Python callers select `VideoAspect.LANDSCAPE` or `VideoAspect.PORTRAIT` from
  `rendering.model`; `VideoAspect(value)` converts supported text values.
  Saved JSON retains `landscape` and `portrait`; existing presets need no migration.
- `VideoOutput.TRANSPARENT` selects the alpha overlay in ProRes 4444 MOV;
  `VideoOutput.OPAQUE` selects the black-background video in H.264 MP4.
  Both come from `rendering.model`; saved JSON retains `transparent` and `opaque`.
- Overlay language is English/German/French, initially following UI language but independently
  selectable. Production previews/frames share localized labels/numbers.
  Replay clocks, source values, geometry, signs and units remain unchanged.
  German and French glyph bounds are checked in every profile/aspect. Known layout names
  translate; Flow Ribbon and G-Orbit retain their identities.

### Assistant and previews

Both steps share a compact ride heading, labeled left-hand controls/summary and
a large right-hand preview. Step one groups export settings, force display and
encoding; presets and compact layout thumbnails remain directly accessible.

Settings order: layout, layout format, export area, position, output dimensions,
output mode, overlay language, frame rate and ride range. Export area offers Full
frame (default) and native Content area through plugin capabilities. Full-frame-only
plugins show a fixed Full frame label. Position is hidden for Content area or a
single fixed placement and restored with its retained value on return to Full frame.
Settings and review show read-only resolved output dimensions and the same codec/extent
file-size estimate; changes update both immediately and refresh the preview.
Review includes layout format, export area and overlay language; position appears
only when applicable. Controls and review labels support English, German and French.

| Interaction            | Contract                                                                                                                           |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Opening                | Two-step modal assistant binds current analysis, graph cursor and smoothing; does not follow workspace changes                     |
| Preview sample         | All five thumbnails and large preview use production RGBA at the exact source sample, independent of video-frame quantization      |
| Preview geometry       | Fit complete output within 960×540 / 540×960 without stretching/cropping; HUD gallery entries always Full frame                    |
| Refresh                | Layout/format/extent, other settings and background changes use a debounced worker; only latest revision applies                   |
| Background             | Checkerboard/light/dark are preview-only; preview needs neither FFmpeg nor encoding                                                |
| Out-of-interval cursor | Retained unchanged; explicit full-recording-context warning                                                                        |
| Review                 | Labeled settings/size summary and large preview; presets/gallery stay on step one; final Export video action chooses destination   |
| Navigation             | Scrollable content, pinned progress/status/ETA and navigation/export actions for smaller/high-DPI desktops and translated settings |
| Close/Escape           | Preserve source sample while open; respect active-encoding cancellation                                                            |

### Analysis and time mapping

- Preparation reuses an identical source/configuration snapshot; otherwise
  `prepare_export_analysis` reuses matching upstream stages and rebuilds affected ones.
  Complete available history precedes interval selection.
- `prepare_export`/`build_previews` accept `RecordingAnalysis`, settings and concrete
  source indices; layouts consume a bound `ExportTimeline`.
  Force/orientation views share prepared buffers; context uses full-history labels
  without per-layout reclassification.
- Orientation is independent of force smoothing. Layout, aspect, export area, position, language, video
  rate and seeking do not recalculate analysis. Running exports/preview workers
  retain bound snapshots independently of later workspace changes.
  This includes custom Gravity/Incline references and subsequent resets: all five
  preview layouts and the encoder consume the same effective basis and tilt.
  Original source directions remain available as evidence; see
  [reference calibration](../development/ANALYSIS_MODELS.md#reference-calibration).
- Source time is index/rate; fractional output positions interpolate adjacent values.
  Inclusive ranges include the final sample interval; duration rounds up to a frame.
- Force readouts use one decimal place in every layout and production preview.
  Curves, pointers, analysis buffers and data exports retain their existing precision.
- 23.976 and 59.94 use exact `24000/1001` and `60000/1001` in timing, frame counts,
  FFmpeg and saved settings. Match the recording and editing timeline's frame rate.
- Default interval uses effective start/end markers; current selection and entire
  recording are alternatives. Plot context outside the exported interval is blank.
- All five layouts use a symmetric lateral instrument/chart scale starting at
  ±1.25 g. The largest absolute valid value in the selected interval expands both
  bounds to the next 0.25 g boundary, without extra padding. Ranges are fixed for
  the entire export; endpoint labels retain quarter-g precision. HUD's separate
  history curves retain their independently fitted ranges.
- Longitudinal scales use the same symmetric quarter-g expansion with a ±1 g
  minimum in all five layouts. Positive and negative peaks share the same extent;
  for example, -1.01 g requires ±1.25 g and +1.26 g requires ±1.5 g.
- All layouts use 1 g as the vertical display reference, including Flying. Numeric
  values, source calibration and analysis remain absolute and unchanged. Vertical
  history charts are symmetric around 1 g, with 5% headroom and a minimum ±0.1 g
  deviation. Their reference line is highlighted; absolute endpoint labels are retained.
- Replay labels retain sample-counter notation. Graphics omit Hz/fps; neither
  identifies the POV video's rate. Technical rates remain in settings/metadata/encoding.

### Geometry, directions and colors

- Full frame fits the complete layout on its canvas, using proportional scaling
  and layout-owned placement. Portrait Ribbon stacks force cards; Column supports
  landscape only. Content area keeps the complete native image without added
  margins or scaling. Previews retain aspect without cropping/stretching.
- The export API accepts a layout/format-supported position or uses that format's
  default. Coordinates and dimensions come from the layout; frame composition,
  large previews, thumbnails and encoder padding use the same selected region.
  The assistant offers a separate localized Position row for applicable Full-frame layouts. Layout/format
  changes retain a supported selection or choose an equivalent edge/corner on the
  same side. Without an equivalent, retain the layout's remembered supported
  position before falling back to its default. Thumbnails use the same policy.
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
  separate major labels. Lateral uses at least ±1.25 g in both formats,
  expanding both sides to the next 0.25 g boundary from the largest absolute actual selected
  peak (for example, 1.26 g → ±1.5 g; 1.54 g → ±1.75 g), independently of major tick spacing.
  Longitudinal uses
  ±1 g in both formats. Before frame generation, its actual valid selected
  samples determine the largest absolute peak: only peaks exceeding 1 g expand
  that scale outward in 0.25 g steps. Padded chart bounds and samples outside the export interval
  do not affect instrument ranges. All ranges remain fixed for the
  entire export. Major tick
  spacing grows for wider ranges to retain readable density; values are never clipped.
- Three thin, wide force histories share a centered time cursor aligned exactly
  with the lateral instrument's zero. Their left/right time spans have equal width
  around that line; baselines and time ticks use the same plot bounds. They use the
  selected interval's independent per-channel scales. In every posture, vertical
  history maps its selected minimum and maximum to the row boundaries, including
  1 g in those bounds. Its 1 g reference line follows that linear mapping; equal
  bounds remain centered. Reference labels follow their lines: 1 g for vertical
  (including inversion), 0 g for lateral and longitudinal. The vertical heading
  and portrait endpoint labels retain fixed anchors.
  Lateral and longitudinal histories use
  zero as their reference and each use their exact
  largest absolute selected value as symmetric bounds, without padding, rounding
  or a minimum force range. Their peaks reach the row boundary: ±31.5 native pixels
  in landscape, ±47 pixels in portrait. Zero-only or missing channels stay on the
  reference when drawn. Labels and readouts retain absolute g values.
  These ranges use valid selected samples, stay fixed during the entire export
  and do not change the large instrument scales. Curve heights therefore show
  variation within each channel, rather than equal g-per-pixel across channels.
  Histories use the
  selected time window. Selecting HUD in the assistant sets a 30-second window
  (15 seconds before/after the cursor), still editable; loaded presets retain their
  saved window. Time ticks appear every second, with labels every five seconds
  (including `0 s`). Time advances left-to-right; vertical respects its inversion,
  lateral is positive-up, and longitudinal acceleration is above zero/braking below.
  Curves break at missing samples and omit context outside the export interval.
  Longitudinal segments change green/red exactly at their zero crossing.
- Independent markers disappear for missing channels. Readouts use existing
  interpolation and prepared context; no speed, gears or vehicle attitude is invented.
- Vertical instruments highlight 1 g as their neutral reference in every posture,
  retaining 0 g, absolute values and the posture-dependent instrument bounds.
- Bright bars along all three instrument scales hold peaks above/below their
  reference: 1.5 seconds, then release toward the reference at 1 g/s. For
  vertical this is 1 g, so unloading such as +0.4 g is held independently of higher
  loading. Lateral and longitudinal channels retain zero as their reference.
  Larger peaks replace the held value immediately. Pointers, lateral dot and
  numeric readouts continue to show current values. Envelopes start at the first
  selected sample, reset at missing samples and use source time, independent of
  seek order and video rate. Missing current values hide their bars and pointers.
- The only position is `full_screen` in both formats. Native 1920×1080/1080×1920
  drawing is exported directly without resizing, for scaling in the video editor.
  Both transparent and opaque output retain these dimensions, including saved
  presets and batches. Preview galleries fit complete output images within common
  display limits while preserving their aspect ratio.
  Static effects are prepared once; moving effects use instrument/history tiles.
  Rendering is independent of seek order and previous frames.
- Unsupported layout keys are rejected in saved presets/jobs; no automatic remapping
  or database cleanup is performed.

### G-Orbit

- Independent signed concentric force arcs: vertical left, longitudinal right,
  lateral upper inner semicircle. The vertical 1 g reference is at the left equator;
  loading/unloading extend toward opposite ends, with absolute numbers inside arcs.
  Vertical instrument bounds use the same Seated/Flying policy as HUD. Vertical
  current arcs and held peaks start at 1 g; other force arcs retain zero.
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

| Estimate             | Contract and limits                                                                                                                             |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| File size            | Live approximate MiB range in settings/review using resolved dimensions, frame count and codec/extent rates; no FFmpeg or trial rendering       |
| Size uncertainty     | Plugin-owned measured planning ranges per codec/extent; missing entries use the shared heuristic; estimates never guarantee bounds              |
| Remaining frame time | Single and batch exports share `ExportProgress`; monotonic elapsed time per submitted frame × pending count; min:sec, including encoder startup |
| ETA states           | Estimating before first frame; finalization after last frame has no predicted duration; cancel/failure/completion clears ETA                    |

`export_video` emits immutable `ExportProgress` snapshots through its callback:
preparing, rendering, finalizing and completed. They carry submitted/total frame
counts, monotonic elapsed time, the actual CPU/GPU backend and a shared
remaining-frame estimate. Completion follows successful file publication. Frame
counts measure input submitted to FFmpeg, not encoded output. Qt workers transport
these snapshots; neither dialog owns a clock or estimates throughput.

The owner-provided HUD references use 1920×1080 and 60000/1001 fps:

| Recording      | Output          | Encoder            | Frames | File bytes     |
| -------------- | --------------- | ------------------ | ------ | -------------- |
| Kraken         | ProRes 4444 MOV | `prores_ks_vulkan` | 9,862  | 15,301,686,528 |
| Kraken (batch) | ProRes 4444 MOV | `prores_ks_vulkan` | 9,544  | 15,856,749,604 |
| Iron Gwazi     | ProRes 4444 MOV | `prores_ks_vulkan` | 8,546  | 13,004,672,088 |
| Voltron Nevera | ProRes 4444 MOV | `prores_ks_vulkan` | 10,353 | 16,397,302,310 |
| Kraken         | H.264 MP4       | `libx264`          | 9,862  | 17,181,504     |
| Kraken (batch) | H.264 MP4       | `libx264`          | 9,544  | 23,256,703     |

The HUD ProRes observations span 0.734–0.801 bytes/pixel/frame; their frame-weighted
mean is 0.76244, rounded to 0.76 with a ±10% planning allowance (0.684–0.836).
HUD CPU H.264 retains 0.00085 with ±50%; both CPU H.264 references fit this planning range.
These reference calibration ranges are unchanged by short test exports.
ProRes rates apply to both CPU and GPU preferences. Other scenes and
portrait output remain unqualified by these references.

The owner-provided Kraken non-HUD ProRes references use 60000/1001 fps,
9,544 frames and `prores_ks_vulkan`. Rates include MOV overhead:

| Layout             | Export area  | Dimensions | File bytes     | Bytes/pixel/frame | Planning range |
| ------------------ | ------------ | ---------- | -------------- | ----------------- | -------------- |
| Flow Ribbon        | Full frame   | 3840×2160  | 17,267,346,554 | 0.21813           | 0.198–0.242    |
| Flow Ribbon        | Content area | 3072×360   | 16,010,922,883 | 1.51692           | 1.368–1.672    |
| Corner Instruments | Full frame   | 3840×2160  | 15,202,085,911 | 0.19204           | 0.171–0.209    |
| Corner Instruments | Content area | 840×1120   | 13,791,547,469 | 1.53598           | 1.386–1.694    |
| G-Orbit            | Full frame   | 3840×2160  | 10,236,947,676 | 0.12932           | 0.117–0.143    |
| G-Orbit            | Content area | 800×800    | 9,153,051,038  | 1.49850           | 1.35–1.65      |
| Four-panel column  | Full frame   | 3840×2160  | 7,032,587,238  | 0.08884           | 0.081–0.099    |
| Four-panel column  | Content area | 960×2160   | 6,069,102,102  | 0.30667           | 0.279–0.341    |

Each measured rate is rounded to two decimal places with a ±10% planning allowance.
These replace the short CPU-clip ranges for the respective codec/extent and apply
to both backend preferences. CPU, unmeasured aspects and other scenes remain
unqualified by these references; further export measurements can refine the ranges.

The owner-provided Kraken non-HUD H.264 references use 60000/1001 fps,
9,544 frames and `libx264`. Rates include MP4 overhead:

| Layout             | Export area  | Dimensions | File bytes | Bytes/pixel/frame | Planning range      |
| ------------------ | ------------ | ---------- | ---------- | ----------------- | ------------------- |
| Flow Ribbon        | Full frame   | 3840×2160  | 24,441,395 | 0.000308753       | 0.0001545–0.0004635 |
| Flow Ribbon        | Content area | 3072×360   | 22,602,237 | 0.002141397       | 0.0010705–0.0032115 |
| Corner Instruments | Full frame   | 3840×2160  | 29,023,934 | 0.000366641       | 0.0001835–0.0005505 |
| Corner Instruments | Content area | 840×1120   | 27,062,402 | 0.003013968       | 0.001507–0.004521   |
| G-Orbit            | Full frame   | 3840×2160  | 8,061,387  | 0.000101834       | 0.000051–0.000153   |
| G-Orbit            | Content area | 800×800    | 6,136,463  | 0.001004634       | 0.0005025–0.0015075 |
| Four-panel column  | Full frame   | 3840×2160  | 69,336,081 | 0.000875879       | 0.000438–0.001314   |
| Four-panel column  | Content area | 960×2160   | 43,889,261 | 0.002217700       | 0.001109–0.003327   |

The owner-provided Voltron Nevera NVENC references use 60000/1001 fps,
10,353 frames and `h264_nvenc`. Rates include MP4 overhead:

| Layout             | Export area  | Dimensions | File bytes  | Bytes/pixel/frame | Planning range      |
| ------------------ | ------------ | ---------- | ----------- | ----------------- | ------------------- |
| Flow Ribbon        | Full frame   | 3840×2160  | 75,440,403  | 0.000878522       | 0.0004395–0.0013185 |
| Flow Ribbon        | Content area | 3072×360   | 76,217,448  | 0.006656784       | 0.0033285–0.0099855 |
| Corner Instruments | Full frame   | 3840×2160  | 78,626,283  | 0.000915623       | 0.000458–0.001374   |
| Corner Instruments | Content area | 840×1120   | 79,139,381  | 0.008125108       | 0.0040625–0.0121875 |
| HUD                | Full frame   | 1920×1080  | 73,904,770  | 0.003442558       | 0.0017215–0.0051645 |
| G-Orbit            | Full frame   | 3840×2160  | 15,774,006  | 0.000183692       | 0.000092–0.000276   |
| G-Orbit            | Content area | 800×800    | 14,267,683  | 0.002153314       | 0.0010765–0.0032295 |
| Four-panel column  | Full frame   | 3840×2160  | 188,122,482 | 0.002190733       | 0.0010955–0.0032865 |
| Four-panel column  | Content area | 960×2160   | 190,277,305 | 0.008863307       | 0.0044315–0.0132945 |

CPU and NVENC H.264 rates are rounded to six decimal places with a ±50% planning
allowance for content/encoder variation. With GPU preference enabled, estimates use
the layout's NVENC rate for the selected extent when present; otherwise they use
its CPU rate for that same extent, followed by the shared heuristic if neither
is measured. Estimation does not probe hardware. An actual CPU fallback can produce
a smaller file than the NVENC planning range. Other scenes, unmeasured aspects and
unmeasured encoders remain unqualified by these references.
The plugin constants retain source intervals, dimensions, encoder settings and
measurement limits. Estimates scale by resolved output pixels and frame count
using the selected planning rates. Other scenes,
durations, languages and unmeasured GPU encoders remain unqualified. These are
approximate ranges, not guaranteed bounds. A missing codec/extent entry uses the
shared heuristic; no rate is borrowed from a different extent.

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
  The single-frame NVENC probe uses 256×256 pixels because some devices reject
  128×128 H.264 input.
  Display selected backend. GPU ProRes never receives CPU `qscale`.
- Frame generation and encoding resolve the same fixed geometry. Content area pipes
  the complete native layout image, including existing empty pixels. Renderer and
  encoder do not crop, scale, add margins/padding or round dimensions; output size
  equals input size. MOV retains transparency; MP4 uses a black background.
  Full frame retains its scaling, canvas and placement. Column's
  Content area remains exactly 960 × 2160 without padding; HUD remains Full frame.
  Previews, assistant dimensions, review and size estimates use the resolved output
  geometry; presets and jobs retain the same typed area choice.
- The save dialog confirms replacement of existing videos. An explicitly confirmed
  replacement atomically publishes the completed staged video on the same filesystem;
  cancellation or failure preserves the original. Other callers and batches default
  to exclusive creation. For new files, use
  same-volume hard links to avoid duplicate large files. Cross-volume or unsupported
  links fall back to exclusive copying; failed/cancelled copies remove partial output.
- Processing stays offline after installation, reusing Pillow. External full FFmpeg
  build/version/checksum is pinned in `ffmpeg.json`; `setup.ps1 -VideoExport` installs it.
  The assistant also accepts an installed executable.
- FFmpeg Browse opens the configured executable's folder, including relative paths
  or missing executables. A directory input opens itself; empty uses native defaults.
  Cancel retains path; choosing a file replaces it.
- Recording bytes, metadata, GPS and source values remain unchanged.
