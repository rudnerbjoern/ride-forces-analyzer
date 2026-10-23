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

| Area                 | Contract                                                                                                                                                        |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| About                | Version, purpose, copyright, licenses, app/RFDB links and independence; live English/German/French and appearance themes                                        |
| Open                 | Local `.forces` / `.zforces` in one dialog; background import/analysis preserves bytes, unknown fields, absent sensors and source arrays                        |
| Failure/cancellation | Retain the last usable recording and service binding                                                                                                            |
| Folder memory        | Successful imports remember their directory across restarts in `preferences.sqlite3` beside the export database; cancellation/failure preserves previous folder |
| Preference failures  | Missing folder/unreadable storage uses dialog defaults; write failures do not block import                                                                      |
| Curves               | Every sample; three independently visible colored channels                                                                                                      |
| Display mode         | Calibrated by default when source directions are usable; otherwise raw with a calibration diagnostic                                                            |
| Direction            | Calibrated lateral +/− = right/left; longitudinal +/− = acceleration/braking; raw x/y/z have unknown units and no rider-direction claims                        |
| Snapshot adoption    | Refresh chart, context, cards, technical details and visible-range extrema together, without repeating preparation                                              |
| Shutdown/rebind      | Release subscriptions; reject late/superseded imports, results and failures, including after reopening                                                          |

**Settings → Application → Restore last file** is off by default and saved only on
Save. Successful imports retain an absolute file path independently of that opt-in.
At startup, an enabled option loads the existing file using the normal worker;
missing files/directories are ignored. Earlier manual import requests take precedence.
Failures preserve the last successful path and use normal import diagnostics.

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

Right-click inside the plot opens a localized menu: set Start, End, Gravity and
Incline; separator; reset each marker to original; separator; reset all ride markers.
Setting uses the nearest sample at the clicked position under the
current zoom; the cursor/selection is unchanged. Right-click does not zoom out.
Inclusive effective bounds require `0 <= start <= end < sample_count`;
invalid start/end actions are disabled. Gravity/Incline accept any admitted source
sample, independently of their order or the ride bounds. Requests use the analysis service and
worker/UI guards; latest changes supersede pending work. Only an adopted successful
result saves all four choices in one transaction. Invalid references retain the
last valid view and saved choices, with a localized error message.
Individual resets preserve other choices; reset all clears both local records and
restores the original source calibration. An absent original marker becomes absent.
Effective marker lines, sample values, context and extrema update together.
Ride-bound changes also refresh replay labels, reset viewport and marker-based
export ranges; calibration-only changes preserve zoom. From/To selection and
original source indices remain unchanged. Opening the menu pauses playback.

`preferences.sqlite3` stores bounds and versioned Gravity/Incline recipes by the
original source SHA-256, independently of file path. Reopening restores valid
local choices through the shared analysis configuration. Missing, invalid or
unreadable entries use source defaults without deleting stored records.
Write failure retains the last saved transaction, keeps the session adjustment and
reports that it was not saved. Closed/rebound sources and stale deliveries cannot
save markers. No source bytes or source JSON fields are rewritten.

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

## Sample playback

- Left/Right shortcuts move one sample while paused. Input fields keep their
  normal keyboard behavior; shortcuts do not seek during playback. Sample bounds
  clamp navigation, and each shortcut belongs to its recording window.
- A fixed-width Play/Pause icon button sits immediately right of the sample slider;
  disabled without a recording or when only one sample exists. Tooltips and
  accessible names follow the English/German/French UI language.
- The adjacent speed dropdown selects 0.5×, 1× or 2×; 1× is the default on import.
  Speed changes preserve continuous position and play/pause state.
- Play advances from the selected integer sample at the chosen multiple of the
  effective recording rate. A monotonic clock determines elapsed samples, independent of UI timer count.
  Delayed callbacks skip to the current sample without slowing playback.
- Cursor, cards, technical details and viewport follow existing sample navigation.
  Raw and calibrated views share the clock; selection and analysis stay unchanged.
- During playback, cursor motion uses continuous elapsed time. A zoomed viewport
  follows once the cursor reaches its midpoint, preserving its width and stopping
  at the recording end. Starting in the right half preserves the cursor's position without an initial
  jump to the center. Values remain at integer samples; no force values are interpolated.
  Time ticks stay anchored to the recording's replay origin instead of being rebuilt
  at moving viewport fractions. Manual seeks retain immediate navigation.
- Manual seeking while playing resets the clock origin to that sample. Pause freezes
  the displayed sample; resuming starts there. There is no force interpolation.
- The range is the whole recording. Stop at the last sample without looping;
  pressing Play there restarts at sample 0. Import/replacement, export opening and
  window close pause playback. Failed import retains the prior recording, paused.

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
| Native caption       | Blue gradient/white force-trace icon with subtle depth; loaded ride name; application name not repeated in toolbar; native controls intact; unsupported caption colors use system defaults             |
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

- Separate north-up view when usable coordinates exist; marks first/last points.
  One point suffices. Original geographic segments support Web Mercator route/map
  alignment; unsupported polar coordinates keep the local WGS84 approximation.
- Missing/out-of-range coordinates remain in source but are omitted from display.
  Break connections at missing fixes or missing/zero/negative/>2 s timestamp intervals.
- Recording replacement or main-window close closes the GPS dialog.
- GPS does not control forces, timing or selection. No invented fixes or confirmed
  speed-color contract. The route remains usable offline.
- **Load map background** explicitly requests only the currently visible OSM area;
  no startup, resize, prefetch or offline-download requests. The static background
  sits behind the route with visible linked © OpenStreetMap contributors attribution.
- `map_background` selects one zoom (0–19) for the viewport's physical pixel size,
  including display scaling, capped at 2048 pixels per image dimension and at most
  64 intersecting 256-pixel tiles. Raster scaling uses smooth transformation;
  resizing an existing image adds no map detail until explicitly reloaded.
  Requests use
  at most 1 MiB per response, sequential 5-second requests and a 20-second loop budget.
  No API key or new dependency is required. Only tile coordinates and the identifying
  User-Agent are sent; no recording, track or timestamps are uploaded.
- Cache individual PNG tiles as BLOBs in application data `map-cache.sqlite3`, keyed
  by provider, zoom, x and y, with expiry, ETag, Last-Modified and last use.
  Read fresh tiles without network requests; revalidate expired tiles. Limit image
  payloads to 100 MiB, evicting least recently used tiles; reclaim freed database
  pages automatically (SQLite metadata is additional). Cache failures do not
  prevent downloading or displaying a map. Respect HTTP expiry, Age,
  no-cache/no-store and conditional ETag/Last-Modified revalidation; absent expiry
  uses seven days. Follow the [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/).
- **Settings → Application → Clear map cache** immediately removes every tile and
  its HTTP metadata, independently of Save/Cancel. Storage reports success/failure
  in the button text; success disables the button. Already displayed maps remain visible.
- Worker failure preserves the route and any existing background. Closing cancels
  the request; revision checks reject late results after close/reopen. Reloading is
  explicit, including after a resize. Unusable coordinates disable map loading.

## Visible-range extrema

- All three channels' min/max over the visible time range, including hidden curves;
  sample boundaries use Select visible range mapping.
- Use the active raw/calibrated channels and selected smoothing for calibrated
  values; retain sample index, replay time and recording seconds.
- Refresh on source, zoom, reset, mode or smoothing. Cursor and From/To edits do not
  affect extrema unless the viewport changes.
- Per-channel table: bold heading, aligned Min/Max and replay times; smaller rows
  retain source sample index and recording seconds.
