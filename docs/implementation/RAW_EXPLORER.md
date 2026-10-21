# Recording explorer

For chart navigation, selection, settings and GPS, see the
[user explorer guide](../user/EXPLORER.md).

Current interaction/display contracts. Architecture owns
[component responsibilities](../architecture/05_building_block_view.md#analysis-boundary),
[service delivery/revisions/lifetime](../architecture/06_runtime_view.md#explorer-analysis-delivery),
[time/view state](../architecture/08_concepts.md#explorer-state-and-time) and
[scientific limits](../architecture/08_concepts.md#scientific-provenance-and-gates).
Product scope belongs in the [roadmap](../ROADMAP.md).

## Loading and presentation

| Area                 | Contract                                                                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| About                | Package version, purpose, copyright, licenses, project/source-app links and independence from Ride Forces; live English/German and light/dark appearance                  |
| Open                 | Local `.forces`, background import/analysis; preserve bytes, unknown fields, absent sensors and source arrays                                                             |
| Failure/cancellation | Retain the last usable recording and service binding                                                                                                                      |
| Folder memory        | Successful file-dialog import remembers its directory across restarts in `preferences.sqlite3` beside the export database; cancellation/failure preserves previous folder |
| Preference failures  | Missing folder/unreadable storage uses dialog defaults; write failures do not block import                                                                                |
| Curves               | Every sample; three independently visible colored channels                                                                                                                |
| Display mode         | Calibrated by default when source directions are usable; otherwise raw with a calibration diagnostic                                                                      |
| Direction            | Calibrated lateral +/− = right/left; longitudinal +/− = acceleration/braking; raw x/y/z have unknown units and no rider-direction claims                                  |
| Snapshot adoption    | Refresh chart, context, cards, technical details and visible-range extrema together, without repeating preparation                                                        |
| Shutdown/rebind      | Release subscriptions; reject late/superseded imports, results and failures, including after reopening                                                                    |

Projection follows the [source-app decision](../architecture/09_architecture_decisions.md#source-app-projection).
Feature availability does not establish per-source scientific verification.
Changing display mode, selection, cursor or viewport does not prepare analysis again.
Missing calibrated values remain unavailable; raw x/y/z appear only in raw mode.

[Vertical airtime context](AIRTIME.md) uses one prepared classification:

- A 10-pixel strip inside the plot's bottom edge follows time zoom/resize and clips
  to the visible interval. The wrapping legend sits below the diagram, above
  navigation; its tooltip identifies provisional thresholds.
- Colors: violet Heavy Gs, neutral Normal Gs, light blue Light Gs, cyan Floater,
  yellow Airtime, orange Strong Airtime, red Ejector; darker equivalents in light mode.
- Vertical visibility controls the strip and legend. Curves retain channel colors
  and original points without additional force filtering.
- The vertical card replaces the static force hint with localized stabilized context
  and matching color; refresh on sample, smoothing, calibration, language or appearance.
- Raw mode retains single-color curves and Unit unknown, without context claims.

## Time, zoom and selection

Time is inferred recording seconds `index / effective_sample_rate`, with
`INFERRED_UNIFORM` and source/default-rate provenance. Integer-rate replay labels
are start-relative `MM:SS.ff`; ff counts samples, not hundredths.
At 50 Hz, `01:31.47` means 91.94 replay seconds. Before-start labels are negative;
fractional rates show explicit seconds. Readouts also retain recording seconds.

| Interaction             | Behavior                                                                                                                                                   |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Initial/reset viewport  | Start/end markers independently, absent boundaries defaulting to 0/N−1                                                                                     |
| Missing/invalid markers | Missing boundaries warn and are not drawn; present invalid indices remain errors                                                                           |
| Initial cursor          | Effective start; inclusive From/To selection remains independent                                                                                           |
| Edit From/To            | Immediately update translucent highlight without changing zoom/cursor; highlight follows zoom/resize, clips to plot and remains a thin mark for one sample |
| Highlight interaction   | Works raw/calibrated and light/dark without intercepting clicks or drag-to-zoom                                                                            |
| Hold up/down arrows     | Repeat until release/range boundary; highlight updates throughout                                                                                          |
| Hold acceleration       | Step 1 initially, 5 after 1 s, 10 after 2 s, 20 after 3 s, 50 after 5 s; release restores single-sample mouse/keyboard steps                               |
| Left click inside plot  | Nearest sample at clicked recording time/current zoom; update slider, cursor and cards                                                                     |
| Click versus drag       | Movement below native drag threshold counts as click; drag-to-zoom/outside clicks do not select                                                            |
| Wheel                   | Time zoom around pointer, factor 1.25 per notch                                                                                                            |
| Time bounds             | Dragging, zoom-to-selection and select-visible-range preserve sample bounds; zoom-out stops at first/last sample; minimum width one sampling interval      |
| Selection round trip    | Snap within 1e-9 sample units                                                                                                                              |
| Source markers          | Labeled start/end/gravity/incline; hide outside viewport without changing indices                                                                          |

Force bounds remain fixed across the complete displayed recording: signed channel
extrema plus 5% outward padding, including zero. All-zero raw data uses [−1, 1];
calibrated bounds include at least [−1.05, 1.05], with explicit −1/0/+1 g labels.
No vertical zoom.

## Smoothing

- Odd centered mean, 1–51 samples; default 11 on successful open; 1 disables filtering.
- Start from unfiltered projection; shorten/renormalize edge windows.
- Display sample count and ±time support at the actual rate. Update while dragging;
  right-click restores 11. Raw mode disables the control but retains its setting
  until another recording opens.
- Background recomputation retains source/time, projection and independent
  orientation, rebuilding only dependent stages. Curves/cards/context remain at the
  last complete result while pending; only the newest matching source/revision/UI
  intent is applied on the UI thread.
- Failure clears pending, reports the error, retains prior values/configuration and
  restores the smoothing control. Time, selection, cursor and GPS remain unchanged.
- Provenance retains algorithm/window/calculation time. Strong smoothing can suppress
  short peaks; 5–11 samples at 50 Hz is an exploration recommendation, not a standard.

## Workspace and metadata

| Area                 | Contract                                                                                                                                                                                               |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Default size         | Requested 1280×820; Windows can reduce it to accommodate available desktop/native frame                                                                                                                |
| Main layout          | Global Open/GPS/notes/Inspector; local calibration/zoom/curve controls; current-value cards below chart                                                                                                |
| Inspector groups     | Display, Selection, Visible range extrema, Recording, Technical details                                                                                                                                |
| Normal desktop       | Chart adapts to workspace height; controls/cards visible without plot-area scrolling, including 1280×720                                                                                               |
| Very small workspace | 240-pixel chart minimum; scrolling keeps controls reachable                                                                                                                                            |
| Compact mode         | Below 1080 pixels width, Inspector switches views; scrolling keeps controls reachable at 720×480                                                                                                       |
| Technical details    | Expandable localized source/processing/current-sample groups; aligned label/value tables, individual processing lines, retained numeric precision/diagnostics; notes action reveals/scrolls to details |
| Literal text         | Device metadata escaped; original diagnostics selectable                                                                                                                                               |
| Sliders              | Narrow track/handle only                                                                                                                                                                               |
| Native caption       | Force-trace icon and loaded ride name; application name not repeated in toolbar; native controls intact; unsupported caption colors use system defaults                                                |
| Status bar           | Application version permanently at bottom right                                                                                                                                                        |

Settings → Application selects Dark/Light/System and UI language. Save applies and
persists both; Cancel preserves choices. Startup restores saved choices, otherwise
OS language (German, English fallback) and System appearance; `AppSettings` can
explicitly override language.

- Shared palette/styles cover controls, disabled/selected states, tables, lists,
  tooltips, dialogs and GPS. Charts have scheme-specific backgrounds, axes,
  force/raw colors and markers; light text/channel/marker colors meet 4.5:1
  contrast against the white chart panel. Native caption follows the scheme when supported.
- Appearance/language changes preserve source/analysis, values, sample, hidden
  curves, selection, zoom and smoothing.
- Export previews/videos retain production colors, separate preview-background
  selection and export settings, independently of application appearance.
- German numeric readouts use decimal commas; replay sample-counter notation stays
  unchanged. Known metadata labels/diagnostic explanations are localized; source
  values, codes and paths remain unchanged. See [localization](../development/LOCALIZATION.md).
- Show available Ride, Park, Train, Row and Seat as plain text, retaining ordered
  duplicates and numeric tokens. Omit absent/blank fields; infer nothing from
  filenames/GPS. Weather remains accessible through importer metadata APIs.

## GPS overview

- Separate offline north-up view when usable coordinates exist; local WGS84
  approximation preserves proportions and marks first/last points. One point suffices.
- Missing/out-of-range coordinates remain in source but are omitted from display.
  Break connections at missing fixes or missing/zero/negative/>2 s timestamp intervals.
- Recording replacement or main-window close closes the GPS dialog.
- GPS does not control forces, timing or selection. No base map, network, invented
  fixes or confirmed speed-color contract.

## Visible-range extrema

- All three channels' min/max over the visible time range, including hidden curves;
  sample boundaries use Select visible range mapping.
- Use the active raw/calibrated channels and selected smoothing for calibrated
  values; retain sample index, replay time and recording seconds.
- Refresh on source, zoom, reset, mode or smoothing. Cursor and From/To edits do not
  affect extrema unless the viewport changes.
- Per-channel table: bold heading, aligned Min/Max and replay times; smaller rows
  retain source sample index and recording seconds.
