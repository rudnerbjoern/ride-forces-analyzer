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

The Qt-independent `explorer` package separates bound presentation state,
text/HTML formatting, inclusive selections and loading. Existing imports of
`ExplorerData`, `SampleRange`, `load_recording`, `present_recording` and
`failure_text` remain available from the package. Qt workers stay in `ui.explorer.loading`.

| Area                 | Contract                                                                                                                                                                                              |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| About                | Version, purpose, copyright, licenses, app/RFDB links and independence; live English/German/French and appearance themes                                                                              |
| Import               | Main toolbar, local file drops and external file requests archive `.forces` / `.zforces` before loading Library bytes; multiple selections import all files and open only the first successful result |
| Failure/cancellation | Retain the last usable recording and service binding                                                                                                                                                  |
| Folder memory        | Successful imports remember their directory across restarts in `preferences.sqlite3` beside the export database; cancellation/failure preserves previous folder                                       |
| Preference failures  | Missing folder/unreadable storage uses dialog defaults; write failures do not block import                                                                                                            |
| Curves               | Every sample; three directional/raw channels and an optional independently visible Combined curve                                                                                                     |
| Display mode         | Calibrated by default when source directions are usable; otherwise raw with a calibration diagnostic                                                                                                  |
| Direction            | Calibrated lateral +/− = right/left; longitudinal +/− = acceleration/braking; raw x/y/z have unknown units and no rider-direction claims                                                              |
| Snapshot adoption    | Refresh chart, context, cards, technical details and visible-range extrema together, without repeating preparation                                                                                    |
| Shutdown/rebind      | Release subscriptions; reject late/superseded imports, results and failures, including after reopening                                                                                                |

**Settings → Application → Restore last file** is off by default and saved only on
Save. Successful loads retain the Library source SHA-256 independently of that
opt-in. Startup reopens archived bytes; removed entries are skipped. Saved
paths use the archive-first import worker. Earlier manual requests take precedence.
Import failures preserve the previous recording and last successful identity.

Projection follows the [source-app decision](../architecture/09_architecture_decisions.md#source-app-projection).
Feature availability does not establish per-source scientific verification.
Changing display mode, selection, cursor or viewport does not prepare analysis again.
Missing calibrated values remain unavailable; raw x/y/z appear only in raw mode.

Combined reads the prepared smoothing buffer. Its violet curve starts off per
recording; raw view hides its checkbox. Usable calibrated samples are required.
Choices survive mode/smoothing changes; missing samples leave gaps.

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
Individual resets preserve other choices; reset all restores the original bounds
and source calibration, clearing preference overrides or replacing the Library's
current recipe. An absent original marker becomes absent.
Effective marker lines, sample values, context and extrema update together.
Ride-bound changes also refresh replay labels, reset viewport and marker-based
export ranges; calibration-only changes preserve zoom. From/To selection and
original source indices remain unchanged. Opening the menu pauses playback.

The [Library marker contract](../development/LIBRARY.md#current-recording-markers)
owns persistence, initial preference admission and source/default recovery. Invalid
Library markers fail opening rather than falling back to stale preferences.
Write failure retains the saved transaction, keeps the session adjustment and
reports that it was not saved. Closed/rebound sources and stale deliveries cannot
save markers.

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
Combined extrema are included only while its curve is enabled. No vertical zoom.

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
| Main layout          | Global Import/GPS/notes/Inspector; local calibration/zoom/curve controls; current-value cards below chart                                                                                              |
| Inspector groups     | Display, Selection, Visible range extrema, Recording, Technical details                                                                                                                                |
| Normal desktop       | Chart adapts to workspace height; controls/cards visible without plot-area scrolling, including 1280×720                                                                                               |
| Very small workspace | 240-pixel chart minimum; scrolling keeps controls reachable                                                                                                                                            |
| Compact mode         | Below 1080 pixels width, Inspector switches views; scrolling keeps controls reachable at 720×480                                                                                                       |
| Technical details    | Expandable localized source/processing/current-sample groups; aligned label/value tables, individual processing lines, retained numeric precision/diagnostics; notes action reveals/scrolls to details |
| Literal text         | Device metadata escaped; original diagnostics selectable                                                                                                                                               |
| Sliders              | Narrow track/handle only                                                                                                                                                                               |
| Native caption       | Blue gradient/white force-trace icon with subtle depth; loaded ride name; application name not repeated in toolbar; native controls intact; unsupported caption colors use system defaults             |
| Status bar           | Application version permanently at bottom right                                                                                                                                                        |

Settings → Application selects a workspace theme and UI language. Appearance previews
immediately; Save persists the choices and Cancel restores the previous theme.
Settings sections scroll when needed; Save/Cancel stay visible outside the scroll
area, so content changes do not force the dialog beyond the available screen.
Sections keep their natural height; additional window space stays below them.
Startup restores valid saved choices, otherwise the registered OS language (English
fallback) and System appearance. System follows Qt's effective OS light/dark
scheme, including later OS changes; an unknown scheme uses dark. Explicit theme
choices override System. `AppSettings` can explicitly override language.
Dropdowns fit complete translated choices and their arrows after language changes.

## Library interactions

The toolbar's Library toggle shows an adjustable left panel, collapsed by default.
The chart takes priority: hidden content reserves no sidebar space and does not
increase the window's minimum size. Expanding/collapsing restores the available
chart area at the same window size; details and dialogs add no permanent pane.
The main **Import…** action archives `.forces` / `.zforces` files off the GUI
thread and opens their Library bytes. The panel has no separate import button.
Multiple selections or drops archive all files and open only the first successful
result in the current Explorer. An explicit new-window import opens just that
first result in one additional window. Failures appear in the status bar and
Library details without stopping the other files or adding an import-log field. Compact entries group recordings by recording-local day, newest
first, with unknown dates last. Ties use import time and source digest for stable
ordering. Each shows an emphasized ride name, a muted park
name and a local clock/export summary. Long names are elided with full tooltips.
A small icon on the right displays the stored workflow status through a localized
tooltip and accessible name; only the current icon is permanently visible.
Clicking the frameless icon opens a rounded foreground layer using theme
background/border colors. Its six frameless icons follow workflow order; the
highlighted current state stays at the clicked icon's position, with earlier/later
steps to its left/right. Choosing any state saves immediately and closes the layer.
Escape or outside click dismisses it unchanged; failed writes retain the old state
and explain the failure. No recording load, selection, chart or list-layout change
is required. Status remains manual, including backwards moves and skipping steps.
A small frameless link icon sits above the workflow icon in the same narrow column.
It uses the theme's muted colour without saved links and accent colour with links;
selected entries use the theme's selection text colour to retain contrast.
It opens that recording's link dialog without selecting/loading it;
link additions/removals refresh indicators across open Library panels. The existing
**Video links…** context action remains available for adding the first link. Add
prepares a new URL/label; selecting an existing row edits that link. Save persists
only the current form, Remove deletes only that link, and Cancel/Escape closes
without saving the current draft. Each saved list entry has a link icon that opens
its HTTP/HTTPS address in the default browser independently of selection and unsaved
edits. Invalid saved addresses disable the action; launch failures are explained. Errors preserve input. Links need
no online verification and do not change workflow status. Settings → Library
manages ordered label options with Save/Cancel, including a deliberately empty
list. Existing link labels survive renamed/removed options; the link dropdown
always offers an unset value and retains its saved label.
Settings → Library also provides paired **Backup…** / **Restore…** actions using
native ZIP pickers and cancellable background workers. Backups include saved
Library data and label choices, excluding unsaved drafts and external videos or
overlays. Restore requires full-replacement confirmation, validates the archive
before committing and refreshes the Library list and saved label choices. It is an
immediate action; Settings Cancel does not undo a successful restore. Closing
Settings during transfer requests cancellation and waits for safe completion.
**Export history…** opens a separate newest-first attempt list, result details and
saved-settings review. Supported repeats prepare archived bytes and captured
markers/metadata in a worker, then use the existing video review or data save flow.
Missing old source/output paths do not prevent repetition. Unsupported recipes
explain their limitation; every started repeat creates a distinct attempt.
Library/day headings reuse the Inspector section-heading style; entry text uses
the shared body font and theme text/muted colors, including live theme changes.
Selecting a recording opens its stored original in the current workspace; failures
preserve the current chart and explain the problem inside the panel. Read-only
details use a compact label/value table without blank rows for ride/park, readable
recording/import times and seating/device information, with the source filename
below. Recording time retains its source-local clock; import time
uses the viewer's local clock. Technical time-zone fields, the raw numeric source
date and the duplicate UUID are omitted from this summary; source data stays intact.
The park dropdown offers all effective Library parks, all parks and unknown parks.
The workflow dropdown offers all six manual states and All statuses by default.
The search requires every whitespace-separated term in the combined ride/park names,
using Unicode normalization and case folding. Park, workflow status and search combine with AND;
wildcard characters are literal. Empty groups disappear, an empty result is explained,
the search-clear action removes only its text, and the reset icon clears all three
filters. A manual status change immediately removes entries that no longer match,
including in other open Library panels, without reloading the current chart. Filtering reads metadata only and leaves the
chart unchanged. Park/status filters, search, Library selection and scroll position
are shared across open Explorers and inherited by new windows. Receiving these
changes never opens a recording; panel visibility and chart state remain local.
**Properties…**, also available through **Shift+Enter** in the active window,
opens a separate themed dialog for ride, park,
Row, Seat, Train, imported/Seated/Flying posture and notes. Park is an editable
combobox populated with distinct effective names from the whole Library on each
opening. Its dropdown offers direct selection; typing filters case-insensitive
substring suggestions that Enter accepts without saving the dialog. New names
remain valid free text. Source placeholders
distinguish inherited text from additions. Save/reset persist current additions;
Cancel discards unsaved input. Errors keep the input visible. Original details and
saved additions remain separately readable in the Library. The workspace and new
exports use effective values; the original bytes, dates and source metadata stay
intact. The posture selector retains unfamiliar source values; only an explicit
override chooses Seated/Flying. Reset clears all additions and notes, restoring
source values. Matching external file opens restore the Library additions as well.
Hiding the Library releases its layout space without changing the loaded recording, selection
or chart viewport; park, workflow-status and search choices are retained.
A recording has at most one Explorer window. Repeated opens, including explicit
new-window actions and byte-identical external inputs, activate its existing window
without replacing its data/view state. Pending archive loads share the same rule.
Opening a recording selects its matching row and scrolls it into view within the
active filters. Expanding the collapsed panel reveals the selection again
without another load. List refreshes and language changes preserve selection.

Right-clicking a recording selects that entry and offers **Open in new window…**,
**Properties…**, **Video links…**, **Export history…**, then a separator and
**Remove…**. The themed actions have icons, replacing the buttons below the list.
Day headings and empty space have no menu. Metadata editing stays disabled until
the selected source loads successfully. All captions, tooltips and accessible
names use the existing English/German/French localization.

**Open in new window…** opens the archived recording with its current additions
and markers in another Explorer in the same application instance. It needs no
external file. Each window owns analysis, playback and chart state; language and
appearance remain shared.

**Remove…** has a trash icon and opens confirmation naming the recording and its
permanently removed archived bytes, metadata, markers, video links and export
history. Both Yes/No buttons have matching icons; **No** is the default. Cancellation
preserves all data. Running exports block removal. Failure retains the entry and
shows an explanation; success refreshes filters and lists across all open Explorer
windows, including hidden panels, through the shared Library change notification.
Cancelled/failed removals publish no change. Loaded recordings, zoom, selection
range and playback stay unchanged; the removed Library selection/details disappear.
External originals and exported media are never deleted.
The [Library service contracts](../development/LIBRARY.md) own storage validation,
the six manual workflow states, label defaults and snapshot compatibility.

## Workspace appearance

The loaded heading combines ride and optional park names, with device/sample/rate
metadata on a shared baseline. Calibration and curve visibility occupy one row;
the three icon-only view controls sit at its right edge with translated tooltips
and accessible names. Calibrated plots show dashed 0 g and 1 g guides within the
existing value range; raw views omit them. GPS status and attribution share the
bottom action row, with Close pinned at its right edge.

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
- Opening GPS restores the visible background automatically when all required
  tiles are fresh in the persistent cache, including after application restart.
  Missing or expired tiles leave the route visible without network access.
  Cache-only misses are normal control flow and do not create error-log entries.
- **Load map background** explicitly requests only the currently visible OSM area;
  no startup, resize, prefetch or offline-download requests. The static background
  sits behind the route with visible linked © OpenStreetMap contributors attribution.
- `gps.map_background` selects one zoom (0–19) for the viewport's physical pixel size,
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
