# 4K ride overlay export

Layout drawing is split into individual built-in modules with a small renderer
protocol and explicit registration. See the [layout API](../development/EXPORT_LAYOUTS.md)
for extension steps; persisted profile keys and output appearance remain unchanged.
Each layout's named, commented constants define its visual styling, including its
portrait variants and, for G-Orbit, peak timing. Shared renderers use those values.

<!-- cspell:words qscale -->

## Supported output

One video per recording in a landscape 3840×2160 or portrait 2160×3840 canvas.
Select Flow Ribbon (opening default),
Corner Instruments, Telemetry Capsule, G-Orbit or the original four-panel column.
Manual Onride alignment stays in DaVinci Resolve; no video ingestion,
synchronization, persistent library or general playback milestone is implied.
Small file size and editing compatibility are priorities. ProRes is implemented;
FFV1 is evaluated only. The [deployment view](../architecture/07_deployment_view.md#encoder-installation)
records the concise full-recording/editor compatibility boundary.

See the [Manta G-Orbit demo on YouTube](https://youtu.be/tsRzD416voU) for an example
of the exported template over Onride footage.

## Contracts

- Settings → Export stores a default video frame rate in `preferences.sqlite3`.
  New export assistants use this rate; without a valid preference they use 50 fps.
  Save changes the persistent default; Cancel leaves it unchanged. Temporary
  assistant changes never update the default. Loaded presets and saved batches
  keep their own rates, including the exact `60000/1001` ratio.

- The save dialog suggests the original `.forces` filename stem with `.mov` or
  `.mp4` for the selected output. Successfully completed exports remember their
  destination folder across restarts in `preferences.sqlite3`, independently of
  the recording folder. A missing folder falls back to the dialog default;
  cancellation and failed exports preserve the previous folder.
- Video format selects 16:9 landscape or 9:16 portrait. All five profiles fit
  completely inside the selected canvas. Portrait Ribbon/Capsule use vertical
  force cards; Corner Instruments, G-Orbit and the four-panel column retain their
  complete instruments with proportional scaling and margins. Preview thumbnails
  and review preserve the full canvas aspect ratio without cropping/stretching.
  Frame composition and encoder padding share the same region geometry.
  Presets and immutable batch jobs persist the aspect; older version-1 records
  without the field default to landscape. Mixed-format batches are supported.
- Overlay language selects English/German independently of application language;
  a new assistant initially follows the UI. Presets/jobs snapshot the choice,
  with English as the default for older saved records. Production previews and
  encoded frames use identical localized labels/number formatting. Replay clocks,
  source values, layout geometry, signs and units stay unchanged. German glyph
  bounds are checked in every profile/aspect. Known layout names are translated;
  Flow Ribbon and G-Orbit retain their profile identities.
  The assistant uses a scrollable content area with pinned navigation/export
  actions so translated settings remain reachable on smaller/high-DPI desktops.

- The two-step export assistant snapshots the graph cursor and current smoothing
  on opening. All five thumbnails and the large preview use the production RGBA
  renderer at that exact source sample, independent of video fps quantization.
  Settings/background changes refresh previews in a debounced worker; only the
  latest revision is applied. No FFmpeg or video encode is needed for a preview.
  Checkerboard/light/dark backgrounds are preview-only. Out-of-interval cursors
  remain unchanged and show an explicit full-recording-context warning. Review
  summarizes the actual export interval/settings; destination selection and full
  rendering require the final Export video action. The modal assistant preserves
  the source sample while open. Escape/close respects active encoding cancellation.
- Transparent ProRes 4444 MOV is the default; opaque H.264 MP4 is independent.
  RGBA Pillow frame generation and external FFmpeg encoding remain separate.
  Settings and review show a live approximate file-size range in MiB, using the
  rounded frame count, canvas/overlay area and output codec. This is an uncalibrated
  planning heuristic, not a measured bitrate or guaranteed bound. Motion, detail,
  filtering and CPU/GPU encoding may put the actual size outside that range.
  Estimation needs no FFmpeg and never renders a trial clip.
  During a single-video export, a two-second timer estimates remaining frame time
  from elapsed monotonic time per submitted frame and pending frame count, displayed
  as minutes:seconds. Startup overhead is included. Before the first frame it shows
  an estimating state; after the last frame it shows finalization,
  whose duration is not predicted. Cancellation, failure and completion clear the ETA.
- One shared source position and centered cursor in each time plot; configurable
  1–60 s context, default 12. Compact time plots show three forces plus numeric tilt;
  the original column includes a fourth orientation plot. G-Orbit uses independent
  signed concentric force arcs instead of time plots: vertical left, longitudinal
  right and lateral on the upper inner semicircle. A separate right orientation
  semicircle carries a marker at the measured angle (0° top, 90° right, 180° bottom),
  without stretching the source's 0–180° range or reconstructing attitude from
  forces. Missing tilt has no marker. G-Orbit has no replay footer. Its square
  region uses a circular translucent background with fully transparent corners.
  All force arcs are 30 px thick at landscape size. Vertical and Longitudinal
  extend inward from outer radius 290 px; Lateral extends outward to radius
  212 px while retaining its inner edge. Scale numbers are bold. White 6 px
  current-value bars cross the tracks with dark 12 px outlines. Portrait output
  scales all dimensions proportionally. Numeric readouts sit inside the arcs.
- G-Orbit holds positive and negative peaks independently for 1.5 source-time
  seconds, then releases toward zero at 1 g/s, never below the current magnitude.
  Reaching the held value again restarts its hold; a new larger peak replaces it
  immediately. Peak tracks start at the prepared interval's first sample and reset
  on missing data. Random-access previews and video frames use the same immutable
  source-time envelopes, independent of query order and export fps.
  Peak bars are 4 px wide with dark outlines, using muted cyan/green/orange
  (#008cac/#24a65e/#ad6c2e). Corresponding arc fills use alpha 65/255, composited
  over the track; opaque current arcs and white current markers remain on top.
- Compact panel RGBA is (7,15,25,210), with transparent surroundings and opaque
  vivid cyan/green/orange data, outlined text/curves and visible -1/0/+1 references.
  Flow Ribbon region is (384,1692,3072,360); Corner Instruments (2808,140,840,1120);
  Capsule (768,108,2304,300); G-Orbit (192,1260,800,800), in x/y/width/height pixels.
  Portrait G-Orbit is (240,2412,1188,1188), retaining circular proportions.
  Rounded corners retain transparency. Opaque output composites panels over black.
- Configurable 24/25/30/50/59.94/60 video fps, default 50. The 59.94 option uses
  the exact `60000/1001` ratio for timing, frame counts and FFmpeg, retained as
  that ratio in saved presets/batches. Select a matching 59.94 editing timeline
  for GoPro footage recorded at that rate. Source sample time remains
  index/rate; fractional output positions interpolate adjacent values. Inclusive
  source ranges include the final sample interval; duration rounds up to a frame.
- Export calibrated channels at the current centered-mean setting. Force bounds
  use selected extrema plus 5% outward padding and include -1/0/+1 g labels.
  Every layout defaults to vertical positive-down (seat pressure) and negative-up
  (lifting). G-Orbit uses a left semicircle with zero at its equator and signed
  extremes at the bottom/top. Vertical direction remains manually reversible in
  every layout. Saved presets retain their explicit vertical direction.
  Time advances left-to-right on horizontal axes and bottom-to-top on vertical
  axes: left/bottom is past, right/top is future. Lateral histories use a vertical
  time axis advancing upward, with negative
  (left) forces left of the centered zero axis and positive (right) forces right.
  Current-only lateral instruments indicate left/right horizontally; G-Orbit uses
  its upper semicircle, centered at the top. Both
  directions share the larger absolute selected bound, preserving equal scale.
  This direction is fixed across all themes/aspects/previews. Legacy lateral
  inversion settings remain readable in presets but do not reverse the display;
  the assistant disables lateral inversion. Numeric signs remain unchanged.
  Axis inversion does not negate source values or change right/left/braking signs.
  Longitudinal acceleration (positive) always appears above zero; deceleration /
  braking (negative) always appears below zero, in histories and current-only
  instruments across all themes/aspects. Longitudinal direction is not invertible.
- Replay labels retain source sample-counter notation. Theme graphics omit sample
  rate (Hz) and export frame rate (fps); neither describes the underlying POV
  video's frame rate. Technical rates remain in settings/metadata and encoding.
  Default range uses effective start/end markers; selection and entire
  recording are selectable. Context outside the exported interval stays blank.
- Orientation is the angle of current normalized source gravity to normalized
  stored vertical (0–180°), with clipped cosine. It is not yaw or GPS heading.
  Missing/zero gravity is unavailable and breaks the curve; no forces-derived substitute.
- Probe real NVIDIA encoding: Vulkan ProRes with alpha, NVENC for opaque H.264;
  otherwise use the CPU encoder and display the backend. GPU ProRes must not
  receive the CPU qscale option. Only the selected layout region crosses the raw-frame pipe;
  the encoder pads the remaining transparent/opaque canvas to the selected dimensions.
- Background export provides progress/cancellation; window close requests cancel.
  Existing files are never overwritten. Publish the completed encoder output
  exclusively. Use same-volume hard links to avoid doubling
  large videos; cross-volume publication copies exclusively and removes partial output.
- Processing remains offline after installation. Existing Pillow dependency is
  reused; FFmpeg full build is external and checksum-pinned in ffmpeg.json.
  setup.ps1 -VideoExport installs it; the dialog also accepts an installed executable.
  Original recording bytes, metadata, GPS and source values remain unchanged.
