# Ride overlay video export

<!-- cspell:words libx qscale Bahnschrift -->

Technical output and interaction contracts; see the [user guide](../user/VIDEO_EXPORT.md)
for export/editor instructions and the [layout API](../development/EXPORT_LAYOUTS.md)
for styling/extensions. Architecture owns [component boundaries](../architecture/05_building_block_view.md#video-export-boundary),
[runtime](../architecture/06_runtime_view.md#video-export-runtime),
[snapshot lifetime](../architecture/08_concepts.md#snapshot-lifetime-and-reuse) and
[encoder installation/qualification](../architecture/07_deployment_view.md#encoder-installation);
the [roadmap](../ROADMAP.md) owns planned scope.

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

Four-panel column is landscape-only: its 960×2160 region fills the 3840×2160
canvas height. Other layouts support both aspects. Unsupported combinations are
unavailable in settings and galleries.
[Manta overlay demo](https://youtu.be/0sGiE6F8YlI) shows all five layouts;
the [HUD demo](https://youtu.be/JGcNPKoKU1Q) uses the supplied
[Manta recording](../development/RECORDINGS.md#manta).

## Contracts

### Defaults, destinations and saved settings

- Settings → Export saves the default frame rate in `preferences.sqlite3`; Cancel,
  temporary assistant edits and independently saved preset/batch rates do not alter it.
  `StandardFrameRate` owns exact fractions, labels and enum order (`EXPORT_FRAME_RATES`);
  `DEFAULT_FRAME_RATE` is 50 fps. `FrameRate` also accepts integers 1–120; standard
  integers normalize to enum members. Python fractional rates use enum members;
  JSON/metadata retain integer rates or exact `24000/1001` / `60000/1001` strings.
- Local `render_jobs` defaults to 1, accepts positive integers up to detected logical
  processors (fallback 1), and applies to newly started single/batch exports.
  It is excluded from visual presets and saved batch snapshots.
- Save suggests `<recording stem> - <displayed layout>.mov/.mp4` (e.g. `Manta - HUD.mov`).
  Only success remembers the destination across restarts, separately from the recording
  folder; missing folders use dialog defaults, cancellation/failure retain the old folder.
- Immutable presets/jobs retain aspect, extent, position, overlay language, vertical
  direction and analysis recipe; mixed-aspect/area batches are supported. Omitted optional
  fields use defaults (`extent`: Full frame); missing required/invalid supplied values
  fail. Unsupported layout keys are rejected without remapping or database cleanup.
- `rendering.model` exposes `VideoAspect.LANDSCAPE`/`PORTRAIT` (JSON `landscape`/`portrait`,
  text conversion via `VideoAspect(value)`) and `VideoOutput.TRANSPARENT`/`OPAQUE`
  (JSON `transparent`/`opaque`). These settings require no storage migration.
- Overlay language initially follows UI language, then independently selects EN/DE/FR.
  Frames/previews share translated labels/numbers; replay clocks, geometry, values,
  signs and units do not change. Glyph bounds are checked in every layout/aspect.
  Layout names translate except Flow Ribbon and G-Orbit.

### Assistant and previews

Two-step modal assistant captures analysis, graph cursor and smoothing on opening,
independently of later workspace changes. Both steps use a compact ride heading,
labeled left controls/summary and large right preview. Step one groups export,
force-display and encoding controls with presets and compact layout thumbnails.

Settings order: layout, format, export area, position, read-only output dimensions,
output mode, language, frame rate and ride range. Plugin capabilities select Full
frame/Content area or a fixed Full frame label. Position is hidden for Content area
or a fixed placement; returning to Full frame restores it. Settings/review share
resolved dimensions and a live size range; changes refresh both and the preview.
Review includes format, area, language and applicable position. All controls/labels
support EN/DE/FR. Final Export video opens the destination dialog.

- All thumbnails and the main preview use production RGBA at the exact source sample,
  independently of video-frame quantization. Fit complete output within 960×540 /
  540×960 without cropping/stretching; HUD gallery entries always use Full frame.
- Settings/background changes use a debounced worker; only its latest revision applies.
  Checkerboard/light/dark backgrounds are preview-only; preview needs no FFmpeg/encoding.
- Preview uses `first + round(0.6 * (last - first))` within the selected export range,
  independently of the graph cursor. Range changes select a new sample; other settings
  retain it. Short ranges may round to an endpoint; a single-sample range uses that sample.
  The workspace cursor stays unchanged; Close/Escape respects cancellation.
- Content scrolls while progress/status/ETA and navigation/export actions remain pinned
  on smaller/high-DPI desktops, including translated settings.

### Analysis and time mapping

- `prepare_export_analysis` reuses identical source/configuration snapshots and matching
  upstream stages, rebuilding affected stages. Full history is prepared before selection.
  `prepare_export`/`build_previews` bind `RecordingAnalysis`, settings and source indices
  to an `ExportTimeline`; force/orientation views share buffers and prepared context
  labels without per-layout classification. Orientation is independent of force smoothing.
- Each timeline owns a frozen `ExportSnapshot`: source identity, full analysis recipe,
  inclusive interval, replay origin, smoothing, sample rate, resolved dimensions and
  planned frame count; no computed buffers or recording paths. Rebinding creates a
  matching snapshot. `encoder_command` embeds it as `export_snapshot` beside flat JSON
  video-comment metadata; single/batch exports share it, with no per-video JSON sidecar.
  [Batch reports](EXPORT_BATCHES.md#contracts) retain that snapshot, requested job,
  actual GPU selection, completed bytes and elapsed job duration.
- Layout/aspect/extent/position/language/rate changes and seeking do not recalculate
  analysis. Running exports/previews retain the bound basis/tilt, including custom
  Gravity/Incline references and resets; source directions remain evidence.
  See [reference calibration](../development/ANALYSIS_MODELS.md#reference-calibration).
- Source time is index/rate; fractional positions interpolate adjacent values. Inclusive
  ranges include the final sample interval and round duration up to an encoded frame.
  23.976/59.94 use exact fractions throughout timing, frame counts, FFmpeg and storage;
  match footage/editing rate. Replay labels use sample-counter notation; graphics omit
  Hz/fps, which cannot identify the POV rate. Technical rates remain in settings/metadata.
- Default interval uses effective start/end markers; selection and whole recording are
  alternatives. Plot context outside it is blank. Force readouts use one decimal;
  curves, pointers, analysis buffers and data exports keep their precision.
- Instrument/chart lateral scales start at ±1.25 g; longitudinal scales at ±1 g.
  Valid selected absolute peaks expand both bounds to the next 0.25 g without padding,
  fixed for the export, with quarter-g endpoint labels (e.g. −1.01 → ±1.25 g,
  +1.26 → ±1.5 g). HUD histories use the independent rules below.
- All layouts use an absolute 1 g vertical reference, including Flying; calibration and
  numeric values stay unchanged. Vertical histories are symmetric about 1 g with 5%
  headroom and minimum ±0.1 g deviation, highlighted reference and absolute endpoints;
  HUD histories use the independent rules below.

### Geometry, directions and colors

- Full frame proportionally fits the complete layout at its layout-owned placement;
  portrait Ribbon stacks force cards. Content area retains the complete native image,
  including empty pixels, without scaling, cropping, margins, padding or size rounding.
  Frame composition, previews/thumbnails and encoding use the same resolved geometry.
- API positions must be supported by layout/aspect or use that format's default.
  Changes retain a supported position, then an equivalent same-side edge/corner,
  then that layout's remembered supported position, then default; thumbnails agree.
- Compact plots show three calibrated, centered-mean-smoothed forces plus numeric tilt;
  Column adds orientation. Bounds use selected extrema with 5% outward padding and
  −1/0/+1 g labels, subject to the channel-specific scale rules above.
- Translucent panels have transparent surroundings/rounded corners. Data are opaque:
  cyan vertical, yellow lateral, green/red longitudinal; text/curves have outlines.
  MP4 composites over black. See [design constants](../development/EXPORT_LAYOUTS.md#design-constants).

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

- Frameless gauges: vertical/context left, acceleration/braking right, signed lateral
  below; transparent center, no reticle, and transparent-to-black bottom-history gradient.
  Fine ticks, luminous pointers, colored bloom and soft black shadows overlay footage.
  Bahnschrift Bold values use the scalable fallback when unavailable; context is uppercase.
- Outer-right orientation line spans instrument height: 0° top to 180° bottom, labeled
  only at 0°/45°/90°/135°/180°. A white triangular marker interpolates prepared tilt;
  missing tilt hides the entire line, labels and marker without a placeholder.
- Vertical bounds start at −1.5…+5 g (Seated) or −4…+3 g (explicit `Flying`). Missing
  metadata defaults to Seated in import; other/unavailable positions use the Seated
  display range without altering metadata. Each bound independently expands outward
  in 0.5 g steps for valid selected samples. Equal pixels/g moves zero with bounds;
  inversion mirrors geometry, not values or bounds. Whole/half/quarter ticks are
  long/medium/short; only whole g labels, with integer-stride density reduction for
  wide ranges and exact endpoint marks. Highlight 1 g while retaining 0 g.
- Lateral/longitudinal follow the shared symmetric instrument rules, with four minor
  ticks per major interval. Major spacing grows for readability independently of
  exact force bounds. Padded history bounds and samples outside selection cannot
  expand instruments; values are not clipped.
- Three thin, wide histories share a centered cursor aligned with lateral zero,
  equal past/future widths, common plot/tick bounds and fixed selected per-channel
  ranges, independent of instrument ranges. Vertical fits selected min/max including
  1 g to row boundaries; equal bounds center. Lateral/longitudinal use exact symmetric
  absolute selected peaks with no padding, rounding or minimum range: ±31.5 native
  pixels landscape / ±47 portrait. Zero-only/missing channels stay on the reference
  when drawn. Heights compare variation, not common g/pixel across channels.
- History reference labels follow 1 g vertical (including inversion) and 0 g for
  the others; headings and portrait endpoints keep fixed anchors, with absolute values.
  Selecting HUD sets an editable 30-second window (±15 s); loaded presets keep theirs.
  Ticks: 1 s, labels: 5 s including `0 s`; time left-to-right, vertical follows inversion,
  lateral positive-up, longitudinal acceleration up/braking down. Curves break on gaps,
  omit out-of-interval context and change longitudinal green/red exactly at zero.
- Independent markers disappear on missing channels; readouts use interpolation and
  prepared context. No speed, gears or vehicle attitude is invented.
  Peak bars hold above/below 1 g vertical (including unloading), zero for other channels:
  1.5 source-time seconds, then release toward reference at 1 g/s. Larger peaks replace
  immediately; current pointers, lateral dot and numbers stay live. Envelopes begin at
  first selected sample, reset on gaps and are seek/fps independent; missing current
  values hide bars/pointers.
- Only `full_screen` position; native 1920×1080 / 1080×1920 is exported without resizing
  for either codec, presets or batches. Galleries fit whole images to preview limits.
  Static effects prepare once; moving effects use instrument/history tiles. Rendering
  is independent of prior frames and seek order.

### G-Orbit

- Signed concentric arcs: vertical left, longitudinal right, lateral upper inner
  semicircle. Vertical uses HUD's Seated/Flying bounds and left-equator 1 g reference;
  loading/unloading extend to opposite ends with absolute labels. Current/held vertical
  arcs begin at 1 g, others at zero.
- Separate right orientation semicircle: measured marker at 0° top / 90° right / 180°
  bottom, absent on missing tilt; no stretched/reconstructed attitude. No replay footer.
  Square region, circular translucent background, transparent corners; portrait scales
  proportionally. Bold numbers and white outlined current bars cross the tracks;
  translucent fills sit below opaque current arcs/white markers.
- Positive/negative peaks hold independently for 1.5 source-time seconds, then release
  toward their reference at 1 g/s without falling below current magnitude. Reaching a
  held value restarts hold; larger peaks replace it. Envelopes begin at first selected
  sample, reset on gaps, and give identical random-access results regardless of fps/order.
  Peak bars use dark outlines/muted colors, longitudinal green/red by sign.

### Estimates and progress

Live approximate MiB ranges in settings/review use resolved dimensions, rounded-up
frame count and plugin codec/aspect/extent/backend rates. Estimation never probes
hardware, invokes FFmpeg or renders a trial; ranges are planning aids, not guarantees.
Missing rates use the same-extent fallback policy below, then a shared heuristic.

Single/batch `export_video` callbacks emit immutable `ExportProgress` snapshots:
preparing, rendering, finalizing, completed. They contain submitted/total frames,
monotonic elapsed time, actual CPU/GPU backend and remaining-frame time
(elapsed/submitted × pending, min:sec, including encoder startup). Counts measure
FFmpeg input, not encoded output. ETA is estimating before the first frame,
unpredicted during finalization and cleared on cancel/failure/completion; completion
requires successful publication. Qt workers transport snapshots; dialogs own no clock
or throughput estimator.

On Windows, the explorer's taskbar button mirrors single-video progress or the
batch's equally weighted overall job percentage, including while minimized.
Starting an export shows indeterminate activity until progress is available;
success, failure and cancellation remove it. The UI-owned native adapter waits for
`TaskbarButtonCreated`, restores active state after button recreation and releases
its COM resources on termination/window destruction. Other platforms and unavailable
shell services leave exports unaffected. See Microsoft's
[taskbar progress contract](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-itaskbarlist3-setprogressvalue).

#### File-size calibration evidence

**47 distinct observations:** 16 GPU ProRes, 4 CPU ProRes, 14 CPU H.264 and 13 NVENC.
Each distinct file is counted once, including matching HUD outputs from different
batch folders. Tables retain recording, layout, extent, dimensions, exact frame rate,
frame count, bytes including container overhead, and bytes/(width × height × frames).
Full-frame and Ribbon/Column native-area dimensions establish aspect; older
Corner Instruments/G-Orbit native-area dimensions fit both aspects and cannot do so.

The 16 portrait references use the same Voltron Nevera interval: samples 4000–4999
at 50 Hz → 480 frames, 24000/1001 fps, 20.02 s; `rider_calibrated`, English, vertical
inverted/lateral unchanged, smoothing 11, history 30 s, ride bounds 1571–10206,
Incline 3575, no Gravity override, reference window 5. Placement: Ribbon bottom,
Corners/Orbit bottom-right, HUD full-screen. `run-report.json` agrees with video
bytes, dimensions, frames, rates, encoder tags and embedded snapshots. Landscape
references use 60000/1001 fps; portrait clips do not qualify longer exports/other scenes.

##### Transparent MOV — ProRes 4444 on NVIDIA Vulkan

Encoder: `prores_ks_vulkan`. Retained observations: **16**.

| Layout             | Recording      | Export area           | Dimensions | Frame rate | Frames | File bytes     | Bytes/pixel/frame |
| ------------------ | -------------- | --------------------- | ---------- | ---------- | ------ | -------------- | ----------------- |
| HUD                | Kraken         | Full frame            | 1920×1080  | 60000/1001 | 9,862  | 15,301,686,528 | 0.748254467       |
| HUD                | Kraken         | Full frame            | 1920×1080  | 60000/1001 | 9,544  | 15,856,749,604 | 0.801232862       |
| HUD                | Iron Gwazi     | Full frame            | 1920×1080  | 60000/1001 | 8,546  | 13,004,672,088 | 0.733857156       |
| HUD                | Voltron Nevera | Full frame            | 1920×1080  | 60000/1001 | 10,353 | 16,397,302,310 | 0.763802728       |
| Flow Ribbon        | Kraken         | Full frame            | 3840×2160  | 60000/1001 | 9,544  | 17,267,346,554 | 0.218127388       |
| Flow Ribbon        | Kraken         | Content area          | 3072×360   | 60000/1001 | 9,544  | 16,010,922,883 | 1.516918413       |
| Corner Instruments | Kraken         | Full frame            | 3840×2160  | 60000/1001 | 9,544  | 15,202,085,911 | 0.192038266       |
| Corner Instruments | Kraken         | Content area          | 840×1120   | 60000/1001 | 9,544  | 13,791,547,469 | 1.535978933       |
| G-Orbit            | Kraken         | Full frame            | 3840×2160  | 60000/1001 | 9,544  | 10,236,947,676 | 0.129316838       |
| G-Orbit            | Kraken         | Content area          | 800×800    | 60000/1001 | 9,544  | 9,153,051,038  | 1.498495625       |
| Four-panel column  | Kraken         | Full frame            | 3840×2160  | 60000/1001 | 9,544  | 7,032,587,238  | 0.088838194       |
| Four-panel column  | Kraken         | Content area          | 960×2160   | 60000/1001 | 9,544  | 6,069,102,102  | 0.306668401       |
| Flow Ribbon        | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 2,668,950,544  | 0.670369603       |
| Corner Instruments | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 2,679,877,705  | 0.673114216       |
| HUD                | Voltron Nevera | Full frame (portrait) | 1080×1920  | 24000/1001 | 480    | 903,143,298    | 0.907382589       |
| G-Orbit            | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 1,099,437,272  | 0.276149488       |

##### Transparent MOV — ProRes 4444 on CPU

Encoder: `prores_ks`. Retained observations: **4**.

| Layout             | Recording      | Export area           | Dimensions | Frame rate | Frames | File bytes  | Bytes/pixel/frame |
| ------------------ | -------------- | --------------------- | ---------- | ---------- | ------ | ----------- | ----------------- |
| Flow Ribbon        | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 813,316,855 | 0.204283627       |
| Corner Instruments | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 821,954,307 | 0.206453126       |
| HUD                | Voltron Nevera | Full frame (portrait) | 1080×1920  | 24000/1001 | 480    | 610,934,100 | 0.613801782       |
| G-Orbit            | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 494,918,229 | 0.124310335       |

##### Opaque MP4 — H.264 on CPU

Encoder: `libx264`. Retained observations: **14**.

| Layout             | Recording      | Export area           | Dimensions | Frame rate | Frames | File bytes | Bytes/pixel/frame |
| ------------------ | -------------- | --------------------- | ---------- | ---------- | ------ | ---------- | ----------------- |
| HUD                | Kraken         | Full frame            | 1920×1080  | 60000/1001 | 9,862  | 17,181,504 | 0.000840178       |
| HUD                | Kraken         | Full frame            | 1920×1080  | 60000/1001 | 9,544  | 23,256,703 | 0.001175148       |
| Flow Ribbon        | Kraken         | Full frame            | 3840×2160  | 60000/1001 | 9,544  | 24,441,395 | 0.000308753       |
| Flow Ribbon        | Kraken         | Content area          | 3072×360   | 60000/1001 | 9,544  | 22,602,237 | 0.002141397       |
| Corner Instruments | Kraken         | Full frame            | 3840×2160  | 60000/1001 | 9,544  | 29,023,934 | 0.000366641       |
| Corner Instruments | Kraken         | Content area          | 840×1120   | 60000/1001 | 9,544  | 27,062,402 | 0.003013968       |
| G-Orbit            | Kraken         | Full frame            | 3840×2160  | 60000/1001 | 9,544  | 8,061,387  | 0.000101834       |
| G-Orbit            | Kraken         | Content area          | 800×800    | 60000/1001 | 9,544  | 6,136,463  | 0.001004634       |
| Four-panel column  | Kraken         | Full frame            | 3840×2160  | 60000/1001 | 9,544  | 69,336,081 | 0.000875879       |
| Four-panel column  | Kraken         | Content area          | 960×2160   | 60000/1001 | 9,544  | 43,889,261 | 0.002217700       |
| Flow Ribbon        | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 4,229,764  | 0.001062405       |
| Corner Instruments | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 4,215,813  | 0.001058900       |
| HUD                | Voltron Nevera | Full frame (portrait) | 1080×1920  | 24000/1001 | 480    | 3,254,464  | 0.003269740       |
| G-Orbit            | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 1,484,353  | 0.000372830       |

##### Opaque MP4 — H.264 on NVIDIA NVENC

Encoder: `h264_nvenc`. Retained observations: **13**.

| Layout             | Recording      | Export area           | Dimensions | Frame rate | Frames | File bytes  | Bytes/pixel/frame |
| ------------------ | -------------- | --------------------- | ---------- | ---------- | ------ | ----------- | ----------------- |
| Flow Ribbon        | Voltron Nevera | Full frame            | 3840×2160  | 60000/1001 | 10,353 | 75,440,403  | 0.000878522       |
| Flow Ribbon        | Voltron Nevera | Content area          | 3072×360   | 60000/1001 | 10,353 | 76,217,448  | 0.006656784       |
| Corner Instruments | Voltron Nevera | Full frame            | 3840×2160  | 60000/1001 | 10,353 | 78,626,283  | 0.000915623       |
| Corner Instruments | Voltron Nevera | Content area          | 840×1120   | 60000/1001 | 10,353 | 79,139,381  | 0.008125108       |
| HUD                | Voltron Nevera | Full frame            | 1920×1080  | 60000/1001 | 10,353 | 73,904,770  | 0.003442558       |
| G-Orbit            | Voltron Nevera | Full frame            | 3840×2160  | 60000/1001 | 10,353 | 15,774,006  | 0.000183692       |
| G-Orbit            | Voltron Nevera | Content area          | 800×800    | 60000/1001 | 10,353 | 14,267,683  | 0.002153314       |
| Four-panel column  | Voltron Nevera | Full frame            | 3840×2160  | 60000/1001 | 10,353 | 188,122,482 | 0.002190733       |
| Four-panel column  | Voltron Nevera | Content area          | 960×2160   | 60000/1001 | 10,353 | 190,277,305 | 0.008863307       |
| Flow Ribbon        | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 7,141,078   | 0.001793649       |
| Corner Instruments | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 7,152,713   | 0.001796572       |
| HUD                | Voltron Nevera | Full frame (portrait) | 1080×1920  | 24000/1001 | 480    | 6,386,732   | 0.006416711       |
| G-Orbit            | Voltron Nevera | Full frame (portrait) | 2160×3840  | 24000/1001 | 480    | 2,909,826   | 0.000730871       |

For the matched portrait interval, Vulkan ProRes files are 1.5–3.3 times larger
than CPU files. Ribbon's Full-frame active region is 1680×2240 portrait versus
3072×360 landscape on equal-pixel canvases: 3.4× the area and 3.1× measured
bytes/pixel/frame. That aspect comparison also changes recording/interval/fps,
so it is not a controlled pair.

##### Configured planning ranges

Bytes per output pixel per frame, including overhead. All supported layout/extents
have default ProRes/CPU H.264/NVENC ranges; configuration alone is not qualification.

| Layout             | Export area  | ProRes 4444 | CPU H.264           | NVENC H.264         |
| ------------------ | ------------ | ----------- | ------------------- | ------------------- |
| Flow Ribbon        | Full frame   | 0.198–0.242 | 0.0001545–0.0004635 | 0.0004395–0.0013185 |
| Flow Ribbon        | Content area | 1.368–1.672 | 0.0010705–0.0032115 | 0.0033285–0.0099855 |
| Corner Instruments | Full frame   | 0.171–0.209 | 0.0001835–0.0005505 | 0.000458–0.001374   |
| Corner Instruments | Content area | 1.386–1.694 | 0.001507–0.004521   | 0.0040625–0.0121875 |
| HUD                | Full frame   | 0.684–0.836 | 0.000425–0.001275   | 0.0017215–0.0051645 |
| G-Orbit            | Full frame   | 0.117–0.143 | 0.000051–0.000153   | 0.000092–0.000276   |
| G-Orbit            | Content area | 1.35–1.65   | 0.0005025–0.0015075 | 0.0010765–0.0032295 |
| Four-panel column  | Full frame   | 0.081–0.099 | 0.000438–0.001314   | 0.0010955–0.0032865 |
| Four-panel column  | Content area | 0.279–0.341 | 0.001109–0.003327   | 0.0044315–0.0132945 |

Portrait Full-frame overrides:

| Layout             | GPU ProRes 4444 | CPU ProRes 4444 | CPU H.264           | NVENC H.264         |
| ------------------ | --------------- | --------------- | ------------------- | ------------------- |
| Flow Ribbon        | 0.603–0.737     | 0.18–0.22       | 0.000531–0.001593   | 0.000897–0.002691   |
| Corner Instruments | 0.603–0.737     | 0.189–0.231     | 0.0005295–0.0015885 | 0.0008985–0.0026955 |
| HUD                | 0.819–1.001     | 0.549–0.671     | 0.001635–0.004905   | 0.0032085–0.0096255 |
| G-Orbit            | 0.252–0.308     | 0.108–0.132     | 0.0001865–0.0005595 | 0.0003655–0.0010965 |

- ProRes: round anchor to two decimals, ±10%. The four landscape HUD GPU observations
  span 0.733857156–0.801232862, frame-weighted mean 0.762444717 → 0.76. Outside portrait
  Full-frame CPU overrides, CPU ProRes shares GPU-derived rates without its own
  long-export evidence.
- H.264: CPU/NVENC separate, six-decimal anchors, ±50%; landscape HUD CPU uses 0.00085
  covering both measurements. Short ten-frame development clips do not qualify long exports.
- Multiply selected rates by output pixels × encoded frames. Portrait ProRes uses
  its override, additionally preferring CPU overrides when GPU preference is off;
  absent entries use default ProRes rates. Portrait H.264 prefers its CPU/NVENC rate;
  missing portrait NVENC prefers portrait CPU, then default codec selection. Default
  H.264 uses NVENC for GPU preference, with CPU fallback. All fallbacks stay within
  the selected extent; if none exists, use the shared heuristic. Actual CPU fallback
  can produce smaller files than GPU ranges.

##### Calibration coverage and remaining gaps

| Output / encoder         | Landscape Full frame    | Measured native Content areas | Portrait Full frame                  |
| ------------------------ | ----------------------- | ----------------------------- | ------------------------------------ |
| MOV / `prores_ks_vulkan` | All five layouts        | All four non-HUD layouts      | All four supported layouts (20.02 s) |
| MOV / `prores_ks` (CPU)  | Missing for all layouts | Missing for all four layouts  | All four supported layouts (20.02 s) |
| MP4 / `libx264` (CPU)    | All five layouts        | All four non-HUD layouts      | All four supported layouts (20.02 s) |
| MP4 / `h264_nvenc`       | All five layouts        | All four non-HUD layouts      | All four supported layouts (20.02 s) |

- Missing: landscape/native-area CPU ProRes; explicit portrait Content-area references
  for all encoders. Older Corners/Orbit native-area measurements retain no aspect.
- Portrait Full frame covers all four supported layouts/encoders only for one 20.02-s
  Voltron interval at 23.976 fps. Longer references use 59.94 fps; remaining combinations
  at 23.976 fps and other rates, including default 50 fps, lack equivalent evidence.
- Landscape non-HUD GPU ProRes/CPU H.264 use Kraken; NVENC uses Voltron Nevera.
  HUD GPU ProRes additionally covers Iron Gwazi/Voltron. Broader recording, duration,
  language and hardware coverage remains open; ranges never guarantee those cases.

| Layout             | Full frame                     | Content area                   |
| ------------------ | ------------------------------ | ------------------------------ |
| Flow Ribbon        | 2160×3840 (20.02-s references) | 840×1120 (missing)             |
| Corner Instruments | 2160×3840 (20.02-s references) | 840×1120 (aspect not retained) |
| G-Orbit            | 2160×3840 (20.02-s references) | 800×800 (aspect not retained)  |
| HUD                | 1080×1920 (20.02-s references) | Unsupported                    |

Full-frame portrait references cover all four encoders. Column portrait and HUD
Content area are unsupported, not calibration gaps.

### Encoding and FFmpeg

- Pillow RGBA generation is separate from external FFmpeg encoding. `rendering.parallel.render_region_bytes`
  runs serially for one job, otherwise with bounded threads and independent renderers,
  fonts/images sharing immutable timelines. Ordered prefetch keeps at most job count + 1
  frames outstanding. Cancel/close cancels queued work and joins active renders;
  batch videos remain sequential. Background export reports progress/cancellation.
- NVIDIA Vulkan alpha ProRes/NVENC requires a successful real probe; otherwise CPU.
  Show the selected backend. NVENC's single-frame probe uses 256×256 (some devices
  reject 128×128 H.264); GPU ProRes never receives CPU `qscale`.
- Encoding preserves resolved native Content-area dimensions or pads the Full-frame
  layout region to its canvas. MOV retains alpha; MP4 composites over black.
- Save-dialog confirmation permits atomic replacement via a completed staged file on
  the same filesystem; cancellation/failure preserves the original. Other callers/batches
  default to exclusive creation. New files use same-volume hard links, falling back to
  exclusive copying across volumes/unsupported links; failed/cancelled copies remove
  partial output. Staging beside the destination is cleaned on success/cancel/failure,
  including launches from read-only application directories.
- Processing is offline after installation; source bytes, metadata, GPS and values
  remain unchanged. Windows supports the optional bundled encoder; external full FFmpeg
  version/build/checksum is pinned in `ffmpeg.json`, installed by `setup.ps1 -VideoExport`.
  Linux/macOS use native external `ffmpeg` from PATH/Browse; frozen Linux library paths
  are removed from its process. See [native deployment](../development/RELEASE.md#linux-and-macos-packages).
- Browse starts in the configured executable's folder (also relative/missing paths),
  opens directory inputs directly or uses native defaults for empty input. Cancel
  retains the path; choosing a file replaces it. An installed executable is accepted.
