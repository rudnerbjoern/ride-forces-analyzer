# Airtime context and layout validation

## Tested scope

Native Windows desktop, repository root, 2026-10-19. Working tree on
`feat/column-lateral-timeline`, based on
`65a973261a59cf290f1a3621079ae7da5c2bf6df`, including the airtime source,
tests, configuration, documentation and generated reference images.
This is local working-tree evidence, not a hosted CI result. The full-run source
scope is now committed as `b055fcb`; the adaptive-height adjustment below is
validated separately on top of that commit.

Scope includes source-time airtime classification and context stabilization,
localized labels and shared colors, the explorer context strip and current-value
card, zoom/visibility/theme behavior, left-to-right Column lateral history and
signed longitudinal rendering across the export themes. Original recording
integrity is covered by the full application suite.

## Environment and preparation

- Native Windows Python 3.14.6 and uv 0.13.0.
- Node 26.11.1 and bundled npm 11.20.0 from `.tmp/node-v26.11.1-win-x64`.
  This directory was prepended to PATH only for the validation process.
- Locked Node tools installed with
  `npm ci --no-audit --no-fund --cache .tmp/npm-cache`.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File setup.ps1 -VideoExport`
  synchronized the locked Python environment and installed checksum-verified
  FFmpeg 9.0.2 under `.tmp/ffmpeg/bin`. Native encoding tests were enabled.

## Results

| Check          | Command                                                                    | Result                                    |
| -------------- | -------------------------------------------------------------------------- | ----------------------------------------- |
| Lockfile       | `uv lock --check`                                                          | 44 packages resolved; valid               |
| Lint           | `uv run --locked ruff check .`                                             | Passed                                    |
| Formatting     | `uv run --locked ruff format --check src tests`                            | 132 files formatted                       |
| mypy           | `uv run --locked mypy src`                                                 | 67 source files; no issues                |
| Pyright        | `npm run typecheck`                                                        | 0 errors, 0 warnings                      |
| Type contracts | `npm run test:types`                                                       | 11 passed                                 |
| Dependencies   | `npm run test:dependencies`                                                | 20 passed                                 |
| CI routing     | `node --test tests/ci/changes.test.mjs`                                    | 45 passed                                 |
| Application    | `uv run --locked pytest -q -ra --junitxml=.tmp/full-validation-pytest.xml` | 1,539 passed; 0 skipped; 249.44 s         |
| Documentation  | `npm run test:docs`                                                        | Markdown, spelling and local links passed |

The complete application suite passed, including native GUI, recording integrity,
real video encoding/decoding and cancellation coverage. No Python tests were
skipped. The separate delivery-skill regression suite was not run because its
implementation and dependencies were not changed.

Final documentation checks include this report and the updated airtime contract.
Actual runner output and JUnit evidence are retained in
`.tmp/full-validation-*.log`, `.tmp/full-validation-results.json`,
`.tmp/full-validation-pytest.xml` and `.tmp/documentation-tests.log`.

## Adaptive workspace height

Native Windows, `b055fcb` plus the current `ui/window.py` sizing adjustment,
`tests/ui/test_explorer.py` regression and accompanying documentation/screenshots.
The chart ignores its old preferred height while retaining its explicit readable
minimum; controls are not hidden and scrollbar policies are not forced off.
At `9ecf659` plus the current legend placement change, the same focused commands
also verify that the airtime legend sits below the diagram and above navigation,
and remains visible throughout the resize cases.

```powershell
.venv/Scripts/python.exe -m pytest tests/ui/test_explorer.py::test_chart_shrinks_to_available_height_without_workspace_scrolling tests/ui/test_explorer.py::test_focus_workspace_layout_and_current_value_cards tests/ui/test_explorer.py::test_vertical_context_bar_preserves_curve_and_tracks_viewport -q
.venv/Scripts/python.exe -m ruff check src/ride_forces_analyzer/ui/window.py tests/ui/test_explorer.py
.venv/Scripts/python.exe -m ruff format --check src/ride_forces_analyzer/ui/window.py tests/ui/test_explorer.py
.venv/Scripts/python.exe -m mypy src/ride_forces_analyzer/ui/window.py
.tmp/node-v26.11.1-win-x64/node.exe node_modules/pyright/index.js src/ride_forces_analyzer/ui/window.py tests/ui/test_explorer.py
npm run test:docs
```

Seven GUI cases passed in 17.27 s. Both languages and appearances fit without
chart scrolling at 1600×1100, 1280×820 and 1280×720, including shrink/grow cycles;
controls/value cards remain visible and data/time range/sample remain unchanged.
Existing compact-window and context-strip regressions pass. Ruff, formatting,
strict mypy and Pyright passed. Updated native screenshots show the regular
layout without changing its scroll position. Very small 720×480 windows retain
scrolling to keep controls reachable. The full application suite was not repeated
for this isolated sizing adjustment; its acceptance is limited to these checks.
The legend placement regression passed all seven cases; runner evidence is in
`.tmp/airtime-legend-tests.log` and `.tmp/airtime-legend-types.log`. Reference
screenshots use the same production layout.

## Reproducible application screenshots

Native Windows, `b055fcb` plus the adaptive workspace changes and
`scripts/capture_app_reference.py`, `tests/ui/test_reference_screenshots.py` and
the accompanying image documentation. The script fixes the Voltron source hash,
sample, selection, smoothing, language, font, scaling and export settings, using
isolated temporary preferences and the actual application widgets.

```powershell
.venv/Scripts/python.exe -m pytest tests/ui/test_reference_screenshots.py -q
.venv/Scripts/python.exe scripts/capture_app_reference.py
.venv/Scripts/python.exe -m ruff check scripts/capture_app_reference.py tests/ui/test_reference_screenshots.py
.venv/Scripts/python.exe -m ruff format --check scripts/capture_app_reference.py tests/ui/test_reference_screenshots.py
.venv/Scripts/python.exe -m mypy src scripts/capture_app_reference.py
.tmp/node-v26.11.1-win-x64/node.exe node_modules/pyright/index.js scripts/capture_app_reference.py tests/ui/test_reference_screenshots.py
npm run test:docs
```

Both focused tests passed: repeated captures have identical pixels, personal
preferences and original recording bytes remain unchanged, and a modified source
is rejected before image creation. The three documentation screenshots and their
settings manifest were generated successfully. Ruff, formatting, mypy (68 files),
Pyright and documentation checks passed. This verifies repeatability within the
tested Windows/Qt environment; other Windows, Qt or font versions may differ.
Runner output is retained in `.tmp/app-reference-*.log` and
`.tmp/documentation-tests.log`.

## Chart sample selection

Native Windows, `9ecf659` plus the current legend-spacing and chart-click changes.
The Qt view distinguishes clicks from drag gestures; `ExplorerData.sample_at_time`
owns nearest-sample mapping and recording-bound clamping.

```powershell
.venv/Scripts/python.exe -m pytest tests/ui/test_explorer.py::test_left_click_selects_nearest_sample_in_current_chart_view tests/ui/test_explorer.py::test_zoom_out_stops_at_recording_bounds tests/ui/test_explorer.py::test_mouse_wheel_zooms_time_at_pointer_with_fixed_value_axis tests/explorer/test_data.py::test_nearest_sample_uses_recording_time_and_clamps_bounds -q
.venv/Scripts/python.exe -m ruff check src/ride_forces_analyzer/ui/window.py src/ride_forces_analyzer/explorer.py tests/ui/test_explorer.py tests/explorer/test_data.py
.venv/Scripts/python.exe -m ruff format --check src/ride_forces_analyzer/ui/window.py src/ride_forces_analyzer/explorer.py tests/ui/test_explorer.py tests/explorer/test_data.py
.venv/Scripts/python.exe -m mypy src
.tmp/node-v26.11.1-win-x64/node.exe node_modules/pyright/index.js src/ride_forces_analyzer/ui/window.py src/ride_forces_analyzer/explorer.py tests/ui/test_explorer.py tests/explorer/test_data.py
npm run test:docs
```

Five tests passed: raw/calibrated views, full/zoomed timelines, slider/cursor
updates, small pointer movements, clicks outside the plot, unchanged selection
bounds and drag/wheel zoom behavior. Pure mapping tests cover nearest samples,
recording bounds and rejection of non-finite times. Ruff, formatting, mypy (67
files), Pyright and documentation checks passed. Actual runner evidence is in
`.tmp/chart-click-tests.log`, `.tmp/chart-click-types.log` and
`.tmp/documentation-tests.log`. The complete application suite was not repeated.

## Visible-range extrema presentation

Native Windows, `9ecf659` plus the current UI changes. Channel tables align
Min/Max, bold force values and replay times; smaller rows retain sample indices
and recording seconds. Plain-text extrema formatting remains available. The
inspector derives its interval from the current time viewport and refreshes on
axis changes, independently of the From/To selection and current sample.

```powershell
.venv/Scripts/python.exe -m pytest tests/ui/test_explorer.py::test_visible_extrema_follow_zoom_and_ignore_selection_and_cursor tests/ui/test_explorer.py::test_smoothing_slider_preserves_source_time_and_selection tests/ui/test_explorer.py::test_zoom_out_stops_at_recording_bounds tests/ui/test_explorer.py::test_left_click_selects_nearest_sample_in_current_chart_view -q
.venv/Scripts/python.exe -m pytest tests/ui/test_explorer.py::test_visible_extrema_follow_zoom_and_ignore_selection_and_cursor -q
.venv/Scripts/python.exe scripts/capture_app_reference.py
.venv/Scripts/python.exe -m ruff check src/ride_forces_analyzer/explorer.py src/ride_forces_analyzer/ui/window.py src/ride_forces_analyzer/translations.py tests/ui/test_explorer.py tests/analysis/test_extrema.py
.venv/Scripts/python.exe -m ruff format --check src/ride_forces_analyzer/explorer.py src/ride_forces_analyzer/ui/window.py src/ride_forces_analyzer/translations.py tests/ui/test_explorer.py tests/analysis/test_extrema.py
.venv/Scripts/python.exe -m mypy src
.tmp/node-v26.11.1-win-x64/node.exe node_modules/pyright/index.js src/ride_forces_analyzer/explorer.py src/ride_forces_analyzer/ui/window.py src/ride_forces_analyzer/translations.py tests/ui/test_explorer.py tests/analysis/test_extrema.py
npm run test:docs
```

Five affected cases have passing evidence (four unchanged cases plus the final
visible-range regression): raw/calibrated formatting, smoothing updates,
viewport mapping, zoom/reset, cursor and From/To independence, and compact-window
access. Existing pure formatting/provenance evidence is retained in
`.tmp/extrema-layout-tests.log`. Ruff, formatting, mypy, Pyright and documentation
checks passed. Reference screenshots were refreshed. Current runner evidence is
in `.tmp/visible-extrema-tests.log`, `.tmp/visible-extrema-regression.log`,
`.tmp/visible-extrema-types.log` and
`.tmp/documentation-tests.log`; the full application suite was not repeated.

## Technical details presentation

Native Windows, `9ecf659` plus the current UI changes. Source provenance,
processing and current sample have separate localized headings. Label/value
tables preserve literal metadata, rate/time provenance, numeric precision and
English/German number formatting; processing settings use separate lines.

```powershell
.venv/Scripts/python.exe -m pytest tests/explorer/test_data.py tests/ui/test_explorer.py::test_open_chart_navigation_selection_and_integrity tests/ui/test_explorer.py::test_app_reference_toggle_for_manta_preserves_raw_values_selection_and_time tests/ui/test_explorer.py::test_replay_notation_on_chart_cursor_selection_and_markers tests/ui/test_explorer.py::test_focus_workspace_layout_and_current_value_cards -q
.venv/Scripts/python.exe -m pytest tests/ui/test_explorer.py::test_app_reference_toggle_for_manta_preserves_raw_values_selection_and_time tests/ui/test_explorer.py::test_technical_details_sections_translate_and_update_sample -q
.venv/Scripts/python.exe -m pytest tests/explorer/test_data.py::test_technical_tables_preserve_provenance_precision_and_literal_metadata tests/ui/test_explorer.py::test_technical_details_sections_translate_and_update_sample -q
.venv/Scripts/python.exe -m ruff check src/ride_forces_analyzer/explorer.py src/ride_forces_analyzer/ui/window.py src/ride_forces_analyzer/translations.py tests/ui/test_explorer.py tests/explorer/test_data.py
.venv/Scripts/python.exe -m ruff format --check src/ride_forces_analyzer/explorer.py src/ride_forces_analyzer/ui/window.py src/ride_forces_analyzer/translations.py tests/ui/test_explorer.py tests/explorer/test_data.py
.venv/Scripts/python.exe -m mypy src
.tmp/node-v26.11.1-win-x64/node.exe node_modules/pyright/index.js src/ride_forces_analyzer/explorer.py src/ride_forces_analyzer/ui/window.py src/ride_forces_analyzer/translations.py tests/ui/test_explorer.py tests/explorer/test_data.py
npm run test:docs
```

Passing evidence covers 47 distinct focused cases, including retained successful
cases plus final affected regressions. Literal HTML-like device metadata stays
escaped; current sample updates, raw/calibrated views, replay notation and compact
access remain covered. Ruff, formatting, mypy and Pyright passed. Documentation
checks passed. Native English/German detail previews were visually inspected
under `.tmp/technical-details*.png`. Runner evidence is retained in
`.tmp/technical-details-*.log` and `.tmp/documentation-tests.log`.
The complete application suite was not repeated.

## Selection highlight

Native Windows, `9ecf659` plus the current UI changes. The From/To interval has
a translucent chart highlight using the application selection color. It clips
to the visible plot, follows zoom/resize and marks single samples with a thin
band. It does not intercept chart gestures or change plotted points/cursor.

```powershell
.venv/Scripts/python.exe -m pytest tests/ui/test_explorer.py::test_selection_highlight_tracks_fields_zoom_and_resize_without_changing_data tests/ui/test_explorer.py::test_left_click_selects_nearest_sample_in_current_chart_view tests/ui/test_explorer.py::test_zoom_out_stops_at_recording_bounds tests/ui/test_explorer.py::test_vertical_context_bar_preserves_curve_and_tracks_viewport -q
.venv/Scripts/python.exe -m pytest tests/ui/test_explorer.py::test_selection_highlight_tracks_fields_zoom_and_resize_without_changing_data tests/ui/test_explorer.py::test_new_file_calibration_defaults_on_and_bad_directions_keep_raw_view -q
.venv/Scripts/python.exe scripts/capture_app_reference.py
.venv/Scripts/python.exe -m ruff check src/ride_forces_analyzer/ui/window.py tests/ui/test_explorer.py
.venv/Scripts/python.exe -m ruff format --check src/ride_forces_analyzer/ui/window.py tests/ui/test_explorer.py
.venv/Scripts/python.exe -m mypy src/ride_forces_analyzer/ui/window.py
.tmp/node-v26.11.1-win-x64/node.exe node_modules/pyright/index.js src/ride_forces_analyzer/ui/window.py tests/ui/test_explorer.py
npm run test:docs
```

Passing focused evidence covers seven distinct cases: light/dark and
raw/calibrated geometry, clipping, resize, single-sample visibility, loading
short recordings, click/drag interactions and preservation of airtime bars.
Ruff, formatting, mypy, Pyright and documentation checks passed. Updated native
reference screenshots were visually checked. Runner evidence is retained in
`.tmp/selection-highlight-*.log` and `.tmp/documentation-tests.log`.
The complete application suite was not repeated.

Native spin-button repeat is preserved by updating each field's range only when
its boundary changes. Holding an arrow increases the step size from 1 to 5 after
one second, 10 after two seconds, 20 after three seconds and 50 after five seconds. Release resets the
step size; ordinary keyboard steps remain unchanged. Focused Windows checks:

```powershell
.venv/Scripts/python.exe -m pytest tests/ui/test_explorer.py::test_selection_arrows_accelerate_while_held_and_reset_on_release tests/ui/test_explorer.py::test_selection_highlight_tracks_fields_zoom_and_resize_without_changing_data -q
```

All four hold/release cases (From/To, up/down) and both highlight cases passed.
The four hold cases observe all 1/5/10/20/50-sample increments during a 5.5-second
press, stop after release and verify single-step clicks/keys afterward. Ordered
boundaries remain valid. Ruff, formatting, mypy, Pyright and documentation checks
passed. Actual runner output is retained in `.tmp/selection-acceleration-*.log`.

## Limits

The [airtime thresholds](../implementation/AIRTIME.md) remain provisional
presentation heuristics; passing tests do not establish scientific rider-load
qualification. GPU preference cases can use the supported CPU fallback and do not
qualify every GPU/driver. Installed Windows tests do not establish clean-machine
release qualification. Hosted CI and exact-commit merge gates remain separate.
No staging, commit, push or publication was performed by this validation.
