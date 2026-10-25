# Export layout extensions

<!-- cspell:words Bahnschrift -->

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

For examples of all five rendered layouts in turn over Onride footage, watch the
[Manta overlay demo on YouTube](https://youtu.be/0sGiE6F8YlI). The additional
[Manta HUD demo](https://youtu.be/JGcNPKoKU1Q) shows only HUD.

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
landscape/portrait `LayoutPositions` and a renderer factory. Each format owns a
read-only `regions` mapping from `LayoutPosition` StrEnum members to explicit pixel
regions `(x, y, width, height)`, plus a supported `default` key. Coordinates start
at the canvas's upper-left corner. Position entries may have different sizes.
Use named members such as `LayoutPosition.TOP_LEFT` in code. Their explicit string
values (such as `top_left`) remain stable; parse external values with
`LayoutPosition(value)`. Metadata keys and defaults require enum members.
Mappings are copied; coordinates/dimensions must be integers, coordinates
nonnegative and sizes positive. Plugin construction rejects regions outside the
maximum 3840×2160 landscape or 2160×3840 portrait bounds, including nondefault entries.
`ExportSettings.position` accepts a `LayoutPosition`; `None` selects the format's
default. Unsupported layout/format combinations and raw string positions raise
`ValueError`. Rendering, previews and encoder padding resolve the same region.
`LayoutPositions.select` retains supported positions, otherwise chooses an equivalent
edge/corner on the same vertical or horizontal side. The assistant remembers each
layout's current position for its lifetime. That position supplies an unspecified
axis (Orbit Top right → Ribbon Bottom → Orbit Bottom right); without a remembered
position, the target default supplies it.
Without an equivalent, the default applies. Preview thumbnails and the assistant's
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
profiles use 4K canvases. Switching from a
full-screen layout restores another layout's remembered position when available,
otherwise its default. No corner/edge is inferred from a full-screen position.

`LANDSCAPE_POSITIONS` and `PORTRAIT_POSITIONS` live in each layout module.
Ribbon declares top/bottom, Column left/right, Corners/G-Orbit all four corners,
and HUD full-screen. Each format has one explicit default.
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

HUD owns immutable landscape/portrait pixel geometry, scale subdivisions and
type/color/effect constants. Static force scales, labels and shadows are drawn once.
Dynamic light/shadow layers are cropped to painted pixels plus their effect margin,
within the original instrument/history tile boundaries. Empty tiles skip filtering.
The orientation line and labels reuse prepared ink; only its bug is redrawn.
Premultiplied-alpha blur preserves colored light without dark
fringes. A static transparent-to-black gradient sits behind the bottom histories.
Value readouts use the installed Bahnschrift Bold weight; context labels use
uppercase text. There is no UI dependency or frame-history cache.
A conditional orientation strip occupies the outermost 48 native pixels at the
right edge, aligned to the side instruments' height. It reads channel 3 through
`ExportTimeline.value_at`, maps 0…180° downward and draws only the five 45° marks
and a white triangular bug. The complete strip is omitted for missing orientation,
including gaps at fractional positions; existing instruments are not repositioned.
Instrument scales hold `(low, high, major_step)` bounds. Vertical uses source
`riding_position`: explicit `Flying` selects −4…+3 g; the general range is
−1.5…+5 g. Both bounds fit valid selected extrema independently in 0.5 g steps,
with bounded tick density and exact endpoint ticks. Only whole g values are
labeled on the vertical instrument: whole, half and quarter g ticks use long,
medium and short marks respectively. Wider ranges thin the quarter-g grid with
an integer stride. Unknown/unavailable posture
uses the general display range, without source reclassification. The affine
vertical mapping has equal pixels per g on both sides and supports reversal.
Scale bars reuse `rendering.peaks.PeakEnvelope` with a 1.5-second hold and 1 g/s
release, independently for each sign/channel. Current markers/readouts remain
instantaneous. Envelopes are prepared once from the selected interval, reset
on gaps and preserve deterministic fractional-sample rendering and seeking.
The right instrument uses a ±1.5 g minimum in both aspects. Its range is fitted
once to the absolute longitudinal peak of valid selected samples, without padded
chart bounds or history headroom, and rounded outward using the scale tick policy.
The lateral instrument uses the same actual-peak selection with a ±2 g minimum,
rounded outward in fixed 0.5 g steps. Major/minor tick density stays bounded for
large ranges; endpoint ticks and portrait labels show the resulting exact bounds.
History ranges are fitted once to valid selected samples per channel, separately
from instrument ranges: symmetric zero-centered bounds, 5% headroom, rounded
outward to 0.1 g with a ±0.1 g minimum. Missing values and data outside the export
interval do not affect these ranges; seeking and the visible time window do not
rescale them. Portrait history endpoint labels use these independent bounds.
The histories' time-zero cursor shares the exact x coordinate of `lateral_x(0)`.
Their right boundary mirrors `history_left` around this coordinate, keeping equal
pixels per second before/after zero; curves, baselines and time ticks share the bounds.

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
   text. Use representative video integration rather than a full option matrix.
   Regenerate the fixed-sample [Voltron Nevera reference](../EXPORT_THEMES.md) to review
   intended design changes. Structural changes must preserve existing pixels.

Registry tests also substitute a small custom renderer to verify that composition
uses the plugin interface, rather than recognizing concrete layout classes.
See the [arc42 building blocks](../architecture/05_building_block_view.md) for the
subsystem boundary and [encoder compatibility boundary](../architecture/07_deployment_view.md#encoder-installation) for
current evidence.
