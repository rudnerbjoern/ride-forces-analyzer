# Export layout extensions

For choosing and reading the available layouts, see the
[user layout guide](../user/EXPORT_LAYOUTS.md). This page covers implementation
and extension of the renderers.

Layouts are internal, explicitly registered plugins. No package discovery,
installation, network access or third-party code loading is involved.
`ExportLayout` is a `StrEnum` exposed by `rendering.model`, with `COLUMN`, `RIBBON`,
`CORNERS`, `HUD` and `ORBIT` members. `ExportLayout(value)` converts its stable text
keys. Saved presets retain `column`, `ribbon`, `corners`, `hud` and `orbit`.
The explicit profile registry binds these identifiers to renderers and geometry;
`PROFILES` retains display names and the selector order.

## Files and responsibilities

| File under `src/ride_forces_analyzer/rendering/layouts/` | Responsibility                                                  |
| -------------------------------------------------------- | --------------------------------------------------------------- |
| `orbit.py`                                               | G-Orbit drawing, force arcs, orientation and peak presentation  |
| `column.py`                                              | Four-panel column                                               |
| `ribbon.py`                                              | Flow Ribbon geometry and portrait reflow                        |
| `corners.py`                                             | Stacked Corner Instruments geometry                             |
| `hud.py`                                                 | Full-screen HUD scales, transparent glow and force histories    |
| `charts.py`                                              | Shared three-channel time plots for ribbon and corners          |
| `common.py`                                              | Fonts, text/panel drawing and shared lateral coordinate mapping |
| `contracts.py`                                           | `LayoutPlugin` metadata and `LayoutRenderer` protocol           |
| `registry.py`                                            | Explicit registrations, region lookup and renderer construction |

## Renderer contract

Each layout module exports one immutable `PLUGIN` with its stable key,
landscape/portrait `LayoutPositions`, canvas dimensions and a renderer factory.
Plugins remain independent; shared algorithms live in `common.py`, `charts.py`,
`rendering.scales` and `rendering.peaks`, never in another concrete layout module.
Each supported format owns a
read-only `regions` mapping from `LayoutPosition` StrEnum members to explicit pixel
regions `(x, y, width, height)`, plus a supported `default` key. Coordinates start
at the canvas's upper-left corner. Position entries may have different sizes.
Use named members such as `LayoutPosition.TOP_LEFT` in code. Their explicit string
values (such as `top_left`) remain stable; parse external values with
`LayoutPosition(value)`. Metadata keys and defaults require enum members.
Mappings are copied; coordinates/dimensions must be integers, coordinates
nonnegative and sizes positive. Plugin construction rejects regions outside the
declared canvas, including nondefault entries. Canvases must fit within the maximum
3840×2160 landscape or 2160×3840 portrait dimensions.
`ExportSettings.position` accepts a `LayoutPosition`; `None` selects the format's
default. Unsupported layout/format combinations and raw string positions raise
`ValueError`. Full-frame rendering, previews and encoder padding resolve the same region;
Content area ignores placement and uses its independent native dimensions.
`LayoutPositions.select` retains supported positions, otherwise chooses an equivalent
edge/corner on the same vertical or horizontal side. The assistant remembers each
layout's current position for its lifetime. That position supplies an unspecified
axis (Orbit Top right → Ribbon Bottom → Orbit Bottom right); without a remembered
position, the target default supplies it.
Without an equivalent, a supported remembered position is retained; otherwise the
default applies. Switching Column Left to Ribbon therefore keeps Column's thumbnail
on the left. Preview thumbnails and the assistant's
localized Position selector share this policy on layout/format changes.
Preview workers receive a copy of the remembered positions for their revision.
`PreviewBackground` defines `CHECKER`, `LIGHT` and `DARK` for `build_previews` and
the assistant worker. Their string values are UI data; backgrounds affect previews only.
Saved presets resolve `None` to the current layout/format default and persist the
explicit `LayoutPosition` value. Immutable job snapshots retain it when presets
change; batches pass the saved settings unchanged to export preparation/encoding.
Coordinates remain layout-owned and are not stored in presets/jobs.

`LayoutPosition.FULL_SCREEN` serializes as `full_screen`. HUD uses this single
position with a region covering its native 1920×1080 or 1080×1920 export canvas.
The compositor and encoder retain these dimensions without upscaling; the other
profiles use 4K canvases for Full frame. Switching from a
full-screen layout restores another layout's remembered position when available,
otherwise its default. No corner/edge is inferred from a full-screen position.

`LayoutPlugin.landscape_canvas` and `portrait_canvas` declare full-frame output sizes;
`canvas_dimensions(settings)` resolves them through the registry. Plugins also own
`preferred_window_seconds` (optional selection-time override), `preview_invert_lateral`
(unselected gallery default), and read-only `prores_4444_size_rates`, `h264_size_rates`,
`h264_nvenc_size_rates`, `prores_4444_portrait_size_rates`,
`prores_4444_cpu_portrait_size_rates`, `h264_portrait_size_rates` and
`h264_nvenc_portrait_size_rates`
maps keyed by `ExportExtent` (optional lower/upper bytes per output pixel per frame).
Shared consumers apply these values
without branching on layout names. HUD declares its native canvases, 30-second
selection default and measured estimate rates; Column declares its lateral preview
default. Each layout declares its Full-frame rates and, where supported, separate
`PRORES_4444_CONTENT_SIZE_RATES` / `H264_CONTENT_SIZE_RATES`. Missing/None entries
use the shared planning heuristic; Full-frame rates never fill missing Content-area
rates. Rates need not be configured for both codecs. No measurements are fabricated.
The estimator uses `h264_nvenc_size_rates` for H.264 with GPU preference enabled.
A missing/None NVENC entry uses `h264_size_rates` for the same extent, followed
by the shared heuristic if that is also missing. No other extent supplies rates.
Portrait ProRes first uses `prores_4444_portrait_size_rates` for the selected extent;
a missing/None override uses the default ProRes rate for that same extent.
CPU ProRes preference additionally selects `prores_4444_cpu_portrait_size_rates`
when present. Portrait H.264 uses `h264_portrait_size_rates` for CPU preference
and `h264_nvenc_portrait_size_rates` for GPU preference. A missing portrait NVENC
entry prefers the same-extent portrait CPU rate before default codec fallback.
All portrait overrides require a supported portrait extent. Estimation does not
probe hardware; actual CPU fallback can produce a smaller file than a GPU range.
All declared codec/extent rates use the owner-provided export
references, with separate measurements per codec/extent.
Short portrait references refine only their measured aspect/extent/encoder; the
[export contract](../implementation/VIDEO_EXPORT.md#estimates-and-progress) records
the measurements and their limits. Plugin comments retain encoder settings,
source intervals where known, tested output sizes, observed rate ranges and limits.
ProRes planning ranges use a ±10% allowance; H.264 uses ±50%.
Measurements include container overhead and do not qualify other recordings,
durations, languages, unmeasured aspects or unmeasured GPU encoders.
Rates must be finite, positive
and ordered; a preferred time window must be within 1–60 seconds.

`LANDSCAPE_POSITIONS` and `PORTRAIT_POSITIONS` live in each layout module.
Ribbon declares top/bottom, Column left/right, Corners/G-Orbit all four corners,
and HUD full-screen. Each supported format has one explicit default.
`portrait=None` declares landscape-only support; Column uses this capability.
Consumers query `supported_aspects` and resolve placements through `positions(aspect)`;
unsupported formats are rejected centrally. Gallery/selector entries are unavailable
for unsupported formats; changing to portrait selects a supported layout when needed.
The factory receives an `ExportTimeline`. Its renderer implements
`render_position(position: float) -> Image.Image`, returning a native-sized
RGBA region at an absolute source-sample position, including fractional samples.

Renderers draw their own backgrounds, labels and instruments. Frame composition,
aspect scaling, transparent/opaque canvas handling and placement stay in
`rendering.frames`; encoding stays in `rendering.encoding`. Renderers must not
access Qt widgets, start encoders, mutate recordings or depend on previous render
calls. The timeline retains its immutable analysis snapshot; channel values are
read-only scalar sequences sharing prepared buffers, with None for missing rows.
Use `timeline.context_at(position)` for prepared context rather than classifying
force values in a layout. For time-dependent instruments, derive state from source time, as
`rendering.peaks` does for G-Orbit.

The shared chart base handles trace sampling and axes. Individual chart modules
own native dimensions, plot offsets, stacking and aspect-specific factories.
Portrait Ribbon reuses the stacked chart arrangement with its own style
and portrait constants; editing Corners does not change that profile.
HUD, G-Orbit and Column have independent drawing code.

Shared scale APIs are `rendering.scales.lateral_scale`, `longitudinal_scale`,
`vertical_scale`, `selected_bounds` and `history_extent`. `ExportChannel.reference`
is 1 g for vertical and zero for the other force channels. Renderers use
`rendering.peaks.PeakEnvelope.prepare` for deterministic held peaks derived from
source time, including seeking and fractional positions. The
[export contract](../implementation/VIDEO_EXPORT.md#analysis-and-time-mapping)
owns scale/reference rules; its [HUD](../implementation/VIDEO_EXPORT.md#hud) and
[G-Orbit](../implementation/VIDEO_EXPORT.md#g-orbit) sections own instrument,
history and peak behavior.

HUD owns immutable aspect-specific geometry and drawing constants. Static scales,
labels, shadows and orientation ink are prepared once. Dynamic effect layers are
cropped to their painted tile bounds; empty tiles skip filtering. Premultiplied-alpha
blur preserves colored light without dark fringes. Drawing remains independent of
Qt and previous render calls.

## Output-area geometry

`ExportSettings.extent` requires `ExportExtent.FULL_FRAME` (default) or
`ExportExtent.CONTENT_AREA`. JSON values are `full_frame` / `content_area`.
`LayoutPlugin.landscape_content` / `portrait_content` hold optional `ContentArea`
definitions. Their presence determines `supported_extents(aspect)`; HUD declares
neither and admits Full frame only. Unsupported extents and raw-string enum inputs
are rejected centrally, without identifying layouts by name.

`ContentArea.dimensions` is the renderer's exact native `(width, height)`, including
layout-owned empty pixels. Both must be positive even integers. Content area never
crops, scales, adds margins/padding or rounds dimensions. Native size is independent
of Full-frame placement/scaling. Invalid metadata is rejected rather than padded.
The [geometry contract](../implementation/VIDEO_EXPORT.md#geometry-directions-and-colors)
lists supported output sizes.

`resolve_geometry(settings)` returns an immutable `ExportGeometry`:

- `output_size`: final dimensions, even for the supported codecs.
- `render_size`: native Content-area image or scaled Full-frame layout region.
- `offset`: `(0, 0)` for Content area, selected placement for Full frame.

Example: G-Orbit Content area resolves to `render_size=(800, 800)`,
`offset=(0, 0)` and `output_size=(800, 800)` in either format.
`ExportSettings.dimensions` remains the Full-frame reference canvas; use resolved
geometry for extent-specific dimensions. File-size estimates already use the
resolved output/region sizes and the selected extent's codec rates.

`OverlayRenderer` fixes the resolved geometry for its timeline. Content area checks
the renderer's image size against metadata and returns the complete native image;
a mismatch raises `ValueError`. Output dimensions and layout placement remain
fixed throughout the export, independently of changing sample content.
Full frame scales to `render_size` as needed and
composes at `offset` on its canvas. Opaque output composites onto black.
The ordered serial/parallel encoder pipe carries the native Content-area image;
FFmpeg retains its size without geometric filters. Full frame retains its existing
scaling, placement, canvas padding and codec options. `render_sample` / `render_frame`
use the same dimensions as the encoded output.

`build_previews` renders the same complete output frame at the supplied source sample
and composites a display-only background and fits the image within 960 × 540
(landscape) or 540 × 960 (portrait). These are maximum sizes, not forced aspect
ratios: native Content-area images retain their shape without cropping/stretching.
Checker cells remain square. Miniatures and the main view share this RGB image;
Qt fits it within its available space while preserving aspect.

Each gallery profile resolves the requested extent through plugin capabilities.
A Full-frame-only profile uses Full frame even when the selected profile uses
Content area; HUD thumbnails therefore always show the complete native HD canvas.
Layout/format/extent changes are carried in the immutable preview request;
the controller invalidates the result and rejects superseded worker revisions.
The assistant derives area/position visibility from plugin capabilities. Full-frame-only
plugins show a fixed area label; Content area hides placement without discarding it.
Settings and review display resolved dimensions and matching codec/extent estimates.
Layout format selects the arrangement, not the native Content-area aspect ratio.

Saved presets and bound jobs serialize the extent's enum value. Omitted `extent`
uses `FULL_FRAME`; supplied unsupported combinations remain invalid, including
HUD with `CONTENT_AREA`. Applying a preset restores both area and retained placement.
Batch execution uses the job's immutable settings with the same geometry resolver;
later assistant/preset edits do not change it.

## Design constants

Each profile starts with named uppercase constants and short English descriptions.
Dimensions, placement, plot insets, readout positions, fonts/sizes, channel colors,
background alpha, line/marker widths and text anchors are defined there, in native
pixels before final aspect scaling. Shared algorithms consume the layout's values;
the defaults in `common.py` do not override profile-specific settings.

For example, G-Orbit exposes `FORCE_STROKE_WIDTH`, `FORCE_ARCS`,
`READOUT_POSITIONS`, `NUMBER_FONT_SIZE`, `TICK_FONT_FILE`, `PEAK_FILL_ALPHA`,
`PEAK_HOLD_SECONDS` and `PEAK_RELEASE_G_PER_SECOND`. Peak duration must be finite
and nonnegative; release speed must be finite and positive. Portrait chart geometry
and value font sizes use separate `PORTRAIT_*` constants where needed.

Edit the constants and restart the application or rerun the reference generator.
They are developer templates, not live user settings. Source channel identity,
sample timing, translated catalog keys and mathematical coordinate calculations
remain behavior contracts rather than arbitrary design values.

Export preparation and previews require `RecordingAnalysis`; layouts receive the
bound `ExportTimeline`, never an explorer/presentation object. Render settings
change composition without changing the bound analysis, full-history context,
force interpolation or independent orientation buffers.

## Add or change a layout

1. Edit its module for geometry or drawing changes. Shared primitives belong in
   `common.py` or `charts.py` only when multiple layouts need them.
2. For a new persisted profile, add its member to `ExportLayout` in `contracts.py`
   and its key/title to `PROFILES` in `rendering.model`. Existing keys must remain compatible with
   saved presets and batch jobs.
3. Add the module's `PLUGIN` to `registry.py`. The composer, preview gallery and
   encoder consume the registration without layout-specific branches.
4. Verify registry coverage, region bounds, force directions, alpha and localized
   text for supported formats/positions and English, German and French. Check
   both export areas with changing content, longest labels and stroke/shadow/glow
   extremes; native image bounds must not clip them. Use representative video
   integration rather than a full option matrix.
   Regenerate the fixed-sample [Voltron Nevera reference](../user/EXPORT_LAYOUT_GALLERY.md) to review
   intended design changes. Structural changes must preserve existing pixels.

Registry tests also substitute a small custom renderer to verify that composition
uses the plugin interface, rather than recognizing concrete layout classes.
See the [arc42 building blocks](../architecture/05_building_block_view.md) for the
subsystem boundary and [encoder compatibility boundary](../architecture/07_deployment_view.md#encoder-installation) for
current evidence.
