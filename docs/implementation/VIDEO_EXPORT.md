# 4K ride overlay export

<!-- cspell:words qscale -->

## Owner scope

One video per recording in a landscape 3840×2160 or portrait 2160×3840 canvas.
Select Flow Ribbon (opening default),
Corner Instruments, Telemetry Capsule, G-Orbit or the original four-panel column.
Manual Onride alignment stays in DaVinci Resolve; no video ingestion,
synchronization, persistent library or general playback milestone is implied.
Produce complete Manta, Kraken and Voltron Nevera overlays as validation artifacts.
Small file size and editing compatibility are priorities. ProRes is implemented;
FFV1 is only evaluated, with size/import limits in the validation report.

## Contracts

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
- One shared source position and centered cursor in each time plot; configurable
  1–60 s context, default 12. Compact profiles show three forces plus numeric tilt;
  the original column includes a fourth orientation plot. G-Orbit uses independent
  signed gauges instead of time plots; it never reconstructs attitude from forces.
- Compact panel RGBA is (7,15,25,210), with transparent surroundings and opaque
  vivid cyan/green/orange data, outlined text/curves and visible -1/0/+1 references.
  Flow Ribbon region is (384,1692,3072,360); Corner Instruments (2808,140,840,1120);
  Capsule (768,108,2304,300); G-Orbit (192,1260,1120,792), in x/y/width/height pixels.
  Rounded corners retain transparency. Opaque output composites panels over black.
- Configurable 24/25/30/50/60 video fps, default 50. Source sample time remains
  index/rate; fractional output positions interpolate adjacent values. Inclusive
  source ranges include the final sample interval; duration rounds up to a frame.
- Export calibrated channels at the current centered-mean setting. Force bounds
  use selected extrema plus 5% outward padding and include -1/0/+1 g labels.
  Column vertical/lateral inversion defaults on; compact charts default positive-up.
  G-Orbit gauge directions are fixed and the corresponding inversion controls disabled.
  Axis inversion does not negate source values or change right/left/braking signs.
- Replay labels retain source sample-counter notation; Hz and video fps are
  separate. Default range uses effective start/end markers; selection and entire
  recording are selectable. Context outside the exported interval stays blank.
- Orientation is the angle of current normalized source gravity to normalized
  stored vertical (0–180°), with clipped cosine. It is not yaw or GPS heading.
  Missing/zero gravity is unavailable and breaks the curve; no forces-derived substitute.
- Probe real NVIDIA encoding: Vulkan ProRes with alpha, NVENC for opaque H.264;
  otherwise use the CPU encoder and display the backend. GPU ProRes must not
  receive the CPU qscale option. Only the selected layout region crosses the raw-frame pipe;
  the encoder pads the remaining transparent/opaque canvas to the selected dimensions.
- Background export provides progress/cancellation; window close requests cancel.
  Existing files are never overwritten. Decode every output frame and verify its
  count before exclusive publication. Use same-volume hard links to avoid doubling
  large videos; cross-volume publication copies exclusively and removes partial output.
- Processing remains offline after installation. Existing Pillow dependency is
  reused; FFmpeg full build is external and checksum-pinned in ffmpeg.json.
  setup.ps1 -VideoExport installs it; the dialog also accepts an installed executable.
  Original recording bytes, metadata, GPS and source values remain unchanged.

## Acceptance

Native Windows evidence belongs in [export validation](../validation/VIDEO_EXPORT.md):
independent orientation snapshots, all-original preparation/integrity, frame counts
and interpolation/gaps, actual RGBA positions/polarity, real CPU/GPU 4K encodes and
alpha decode, cancellation/no overwrite, GUI lifecycle and focused strict checks.
Pure rendering checks cover every layout/aspect, translucent panel alpha,
glyphs, signs, negative G-Orbit readings and absent tilt. Representative real
encodes cover both codecs/aspects/backend preferences with all layouts represented;
language geometry and encoder command options have independent checks. The native
layout picker and shared worker lifecycle are tested without multiplying every
profile across the full export workflow.
Inspect rendered frames and the completed three full recordings, including correct
codec, 4K dimensions, 50 fps, expected duration/frame counts and full decode.
Retain the codec compatibility source and distinguish it from an actual Resolve
UI import. A full M6 milestone closure and a new full suite are outside this scope.
