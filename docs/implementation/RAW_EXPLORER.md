# Recording explorer

This document defines current interaction and display contracts. Product scope
belongs in the [roadmap](../ROADMAP.md); scientific boundaries belong in
[analysis concepts](../architecture/08_concepts.md#scientific-provenance-and-gates).

## Loading and presentation

- The toolbar's About dialog shows package version, project purpose, copyright,
  licenses and external project/source-app links. It supports live English/German
  translation and light/dark appearance, and states independence from Ride Forces.
- Open local `.forces` without changing their contents, using a background worker.
  Cancelled/failed imports retain the last usable recording; shutdown drains workers.
  Successful file-dialog imports remember their folder across restarts in the local
  `preferences.sqlite3` database beside the export database. Missing folders or
  unreadable preferences use the dialog's default directory; cancellation and failed
  imports preserve the previous folder. Preference write failures do not block imports.
- Display every sample in three colored, independently visible curves. Raw x/y/z
  retains unknown units. Calibrated forces defaults on whenever source directions
  are usable; otherwise raw display includes a calibration diagnostic.
- Projection and smoothing follow [source-app projection decision](../architecture/09_architecture_decisions.md#source-app-projection).
  Feature availability is independent of per-source scientific verification.
- Calibrated lateral positive/negative means right/left; longitudinal means
  acceleration/braking. Raw values have no rider-direction claims.
- A 10-pixel strip at the bottom inside the plot shows stabilized
  [vertical airtime context](AIRTIME.md) colors: violet Heavy Gs, neutral Normal Gs, light blue Light Gs, cyan Floater,
  yellow Airtime, orange Strong Airtime and red Ejector. A wrapping legend below
  the diagram, above sample navigation, names the categories near the strip;
  its tooltip identifies the provisional thresholds. Light
  appearance uses darker shades of the same hues for contrast. The strip follows the time axis
  when zooming/resizing and clips to the visible interval. Force curves keep their
  normal channel colors and original points, without additional force filtering.
  The vertical visibility control includes the context strip and its legend.
  Raw x/y/z curves keep their existing single colors without airtime claims.
- The vertical value card below the chart shows the current stabilized context
  instead of the static Vertical force hint, using the matching context color
  and localized text. It shares the strip's prepared analysis and refreshes on
  sample, smoothing, calibration, language and appearance changes. Raw mode
  retains Unit unknown without a context classification.
- Preserve original bytes, unknown fields, absent sensors and all source arrays.

## Time, zoom and selection

Internal coordinates are recording seconds `index / effective_sample_rate`, with
INFERRED_UNIFORM time and source/default rate provenance. Integer-rate replay
labels use start-relative `MM:SS.ff`: ff is the sample counter, not hundredths.
At 50 Hz, `01:31.47` is 91.94 replay seconds. Before-start labels are negative;
fractional rates use explicit seconds. Recording seconds remain in the readout.

Initial/reset view uses start/end markers independently, falling back to 0/N-1
for each absent boundary. Missing boundaries produce importer warnings, not drawn
markers. Present invalid indices remain errors. The initial cursor uses effective
start; local inclusive selection is independent. Editing From/To sample immediately
updates a translucent highlight in the chart without changing its zoom or cursor.
The highlight follows zoom/resize, clips to the plot and stays visible as a thin
mark for a single selected sample. It works in raw/calibrated and light/dark views
without intercepting clicks or drag-to-zoom interactions.
Holding either field's up/down arrow repeats sample steps until release or the
valid range boundary; the chart highlight updates throughout. Step size increases
from 1 to 5 after one second, 10 after two seconds, 20 after three seconds and
50 after five seconds.
Release restores single-sample steps for the next click or keyboard step.

A left click inside the plot selects the nearest sample at that recording time,
using the current time zoom, and updates the slider, cursor and value cards.
Small pointer movements below the native drag threshold still count as clicks;
dragging to zoom and clicks outside the plot do not select a sample.
Mouse wheel zooms time around the pointer (1.25 per notch); dragging, zoom to
selection and select visible range preserve sample bounds. Zoom-out stops at the
first/last sample. Minimum view width is one sampling interval. Selection boundary
round trips snap within 1e-9 sample units. Source start/end/gravity/incline markers
are labeled and hidden outside the viewport without modifying their indices.

The force axis is fixed for the displayed complete recording: signed extrema
across channels plus 5% outward padding, including zero. Raw all-zero data uses
[-1, 1]; calibrated bounds include at least [-1.05, 1.05]. Explicit -1/0/+1 g
labels remain visible. No vertical zoom is provided.

## Smoothing

Use odd centered mean windows 1–51, default 11 on each successful open; 1 disables
filtering. Always start from the unfiltered projection; edge windows shorten and
renormalize. Show sample count and ±time support at the actual rate. Update while
dragging; right-click restores 11. Raw mode disables the control but retains its
setting until another recording opens. Time, selection, cursor and GPS are unchanged.
Reference provenance retains algorithm/window/calculation time. Strong smoothing
can suppress short peaks; 5–11 at 50 Hz is an exploration recommendation, not a standard.

## Workspace and metadata

Requested default size is 1280×820; Windows may reduce the shown size when the
available desktop cannot accommodate it and its native frame. The chart-first layout provides global Open/GPS/
notes/Inspector actions, local calibration/zoom/curve controls and current-value
cards below the chart. The right inspector groups Display, Selection,
Visible range extrema, Recording and Technical details.
The chart expands and shrinks with the available workspace height, keeping its
controls and current-value cards visible without plot-area scrolling at normal
desktop sizes (including 1280×720).
At very small sizes, the plot retains a 240-pixel minimum height and scrolling
remains available so that controls are not clipped or hidden.
Technical details group source provenance, processing and the current sample
under separate localized headings. Source fields and sample values use aligned
label/value tables; processing settings use individual lines. Device metadata is
escaped as literal text, and existing numeric precision and diagnostics remain
available. These details are expandable; opening
notes reveals/scrolls to them. Below 1080 pixels width, Inspector switches views;
scroll areas keep all controls reachable at 720×480. Sliders show only their narrow
track and handle. Native caption uses a force-trace icon and loaded ride name;
the application name is not repeated in the toolbar. Unsupported Windows caption
colors retain system defaults; native window controls remain intact.
The status bar permanently displays the application version at the bottom right.

Settings → Application selects Dark, Light or System appearance and UI language.
Save applies and persists both choices; Cancel preserves them. Startup restores
the saved choices, defaulting to OS language and System appearance. Shared application palette/styles cover controls, disabled/selected states,
tables, lists, tooltips, dialogs and GPS. Charts use scheme-specific backgrounds,
axes, force/raw colors and markers; light text/channel/marker colors have at least
4.5:1 contrast against the white chart panel. The main native caption follows the
scheme when Windows supports its color attributes. Changing appearance preserves
recording identity/values, hidden curves, selection, zoom, sample and smoothing.
Export previews/videos retain their production colors and independent preview
background selection; application appearance never changes export settings.

Saving English/German UI language applies immediately while preserving source/analysis,
sample, selection, hidden curves and zoom. German numeric readouts use decimal
commas; replay sample-counter notation stays unchanged. Known metadata labels and
diagnostic explanations are localized; source values, diagnostic codes and paths
are preserved. Complete original diagnostics remain selectable in technical details.
Without a saved choice, startup follows the OS language (German or English
fallback); AppSettings can explicitly override it. See [localization](../development/LOCALIZATION.md).

Show available Ride, Park, Train, Row and Seat fields as plain text, preserving
ordered duplicates and numeric tokens. Omit absent/blank metadata; do not infer it
from filenames or GPS. Weather remains available through the importer metadata API.

## GPS overview

Open a separate offline north-up view when usable coordinates exist. A local
WGS84 approximation preserves proportions and marks
first/last points. Missing/out-of-range coordinates remain in source; omit them
from display and break connections at missing fixes or missing/zero or negative/>2 s
timestamp intervals. One usable point can be displayed. Replacement/main-window
close closes its GPS dialog. GPS never controls force values, timing or selection.
No base map, network, invented fixes or confirmed speed-color contract is provided.

## Visible-range extrema

The inspector's Visible range extrema panel shows all three channels' min/max for
the visible time range, even when a curve is hidden. Sample boundaries follow
the existing Select visible range mapping. Values use the active
raw/calibrated window and include source sample plus replay/recording time.
Results update on source, zoom, reset, mode and smoothing. Moving the cursor or
editing From/To sample does not change the result unless the viewport changes.
Each channel has a table with a bold heading, aligned Min/Max values and replay
times. Smaller detail rows retain the sample index and recording seconds.
Calculation and presentation responsibilities belong to the
[building block view](../architecture/05_building_block_view.md#analysis-boundary).
