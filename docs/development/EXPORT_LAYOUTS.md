# Export layout extensions

Layouts are internal, explicitly registered plugins. No package discovery,
installation, network access or third-party code loading is involved.
The public selection and saved-preset keys remain unchanged.

## Files and responsibilities

| File under `src/ride_forces_analyzer/rendering/layouts/` | Responsibility                                                  |
| -------------------------------------------------------- | --------------------------------------------------------------- |
| `orbit.py`                                               | G-Orbit drawing, force arcs, orientation and peak presentation  |
| `column.py`                                              | Original four-panel column                                      |
| `ribbon.py`                                              | Flow Ribbon geometry and portrait reflow                        |
| `corners.py`                                             | Stacked Corner Instruments geometry                             |
| `capsule.py`                                             | Telemetry Capsule geometry, number sizing and portrait reflow   |
| `charts.py`                                              | Shared three-channel time plots for ribbon, corners and capsule |
| `common.py`                                              | Fonts, text/panel drawing and shared lateral coordinate mapping |
| `contracts.py`                                           | `LayoutPlugin` metadata and `LayoutRenderer` protocol           |
| `registry.py`                                            | Explicit registrations, region lookup and renderer construction |

## Renderer contract

Each layout module exports one immutable `PLUGIN` with its stable key,
landscape/portrait regions `(x, y, width, height)` and a renderer factory.
The factory receives an `ExportTimeline`. Its renderer implements
`render_position(position: float) -> Image.Image`, returning a native-sized
RGBA region at an absolute source-sample position, including fractional samples.

Renderers draw their own backgrounds, labels and instruments. Frame composition,
aspect scaling, transparent/opaque canvas handling and placement stay in
`rendering.frames`; encoding stays in `rendering.encoding`. Renderers must not
access Qt widgets, start encoders, mutate recordings or depend on previous render
calls. For time-dependent instruments, derive state from source time, as
`rendering.peaks` does for G-Orbit.

The shared chart base handles trace sampling and axes. Individual chart modules
own native dimensions, plot offsets, stacking and aspect-specific factories.
Portrait Ribbon/Capsule reuse the stacked chart arrangement with their own style
and portrait constants; editing Corners does not change those profiles.
G-Orbit and Column have independent drawing code.

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

## Add or change a layout

1. Edit its module for geometry or drawing changes. Shared primitives belong in
   `common.py` or `charts.py` only when multiple layouts need them.
2. For a new persisted profile, add its stable key/title to `ExportLayout` and
   `PROFILES` in `rendering.model`. Existing keys must remain compatible with
   saved presets and batch jobs.
3. Add the module's `PLUGIN` to `registry.py`. The composer, preview gallery and
   encoder consume the registration without layout-specific branches.
4. Verify registry coverage, region bounds, force directions, alpha and localized
   text. Use representative video integration rather than a full option matrix.
   Regenerate the fixed-sample [Manta reference](../EXPORT_THEMES.md) to review
   intended design changes. Structural changes must preserve existing pixels.

Registry tests also substitute a small custom renderer to verify that composition
uses the plugin interface, rather than recognizing concrete layout classes.
See the [arc42 building blocks](../architecture/05_building_block_view.md) for the
subsystem boundary and [export verification](../validation/VIDEO_EXPORT.md) for
current evidence.
