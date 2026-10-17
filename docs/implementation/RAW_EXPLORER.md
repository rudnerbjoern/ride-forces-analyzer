# Recording explorer — implemented contracts

The explorer is a usable M4 slice. Reduced M3 has [focused acceptance](../validation/M3.md); M4 library acceptance
remains open; see [roadmap](../ROADMAP.md) and [Windows evidence](../validation/RAW_EXPLORER.md).

## Loading and presentation

- Open local `.forces` through the lossless M2 service in a background worker.
  Cancelled/failed imports retain the last usable recording; shutdown drains workers.
- Display every sample in three colored, independently visible curves. Raw x/y/z
  retains unknown units. Calibrated forces defaults on whenever source directions
  are usable; otherwise raw display includes a calibration diagnostic.
- Projection and smoothing follow [ADR 0006](../decisions/0006-app-reference-projection.md).
  Feature availability is independent of per-source scientific verification.
- Calibrated lateral positive/negative means right/left; longitudinal means
  acceleration/braking. Raw values have no rider-direction claims.
- Preserve original bytes, unknown fields, absent sensors and all source arrays.
  Qt widgets delegate import/scientific calculations to their existing subsystems.

## Time, zoom and selection

Internal coordinates are recording seconds `index / effective_sample_rate`, with
INFERRED_UNIFORM time and source/default rate provenance. Integer-rate replay
labels use start-relative `MM:SS.ff`: ff is the sample counter, not hundredths.
At 50 Hz, `01:31.47` is 91.94 replay seconds. Before-start labels are negative;
fractional rates use explicit seconds. Recording seconds remain in the readout.

Initial/reset view uses start/end markers independently, falling back to 0/N-1
for each absent boundary. Missing boundaries produce importer warnings, not drawn
markers. Present invalid indices remain errors. The initial cursor uses effective
start; local inclusive selection is independent.

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
available desktop cannot accommodate it and its native frame. The dark chart-first layout provides global Open/GPS/
notes/Inspector actions, local calibration/zoom/curve controls and current-value
cards below the chart. The right inspector groups Display, Selection and Recording.
Technical provenance, full-precision values and diagnostics are expandable; opening
notes reveals/scrolls to them. Below 1080 pixels width, Inspector switches views;
scroll areas keep all controls reachable at 720×480. Sliders show only their narrow
track and handle. Native caption uses a force-trace icon and loaded ride name;
the application name is not repeated in the toolbar. Unsupported Windows caption
colors retain system defaults; native window controls remain intact.

Show available Ride, Park, Train, Row and Seat fields as plain text, preserving
ordered duplicates and numeric tokens. Omit absent/blank metadata; do not infer it
from filenames or GPS. Weather remains available through the importer metadata API.

## GPS overview

Open a separate offline north-up view when usable coordinates exist. Pure geometry
preparation uses a local WGS84 approximation; Qt preserves proportions and marks
first/last points. Missing/out-of-range coordinates remain in source; omit them
from display and break connections at missing fixes or missing/zero or negative/>2 s
timestamp intervals. One usable point can be displayed. Replacement/main-window
close closes its GPS dialog. GPS never controls force values, timing or selection.
No base map, network, invented fixes or confirmed speed-color contract is provided.

## Acceptance boundary

Native Windows tests cover startup/custom sizes, resizing, all five originals,
every plotted point, live navigation/smoothing/reset, zoom/selection/markers,
raw fallback, missing metadata, error recovery, responsive imports, GPS lifecycle
and exact source integrity. Visual checks cover wide/compact layouts and native
caption. Retain exact commands/results/platform/scope in the validation report.
Persistent storage, playback, statistics, rendering and export are outside this slice.

The inspector's Selection extrema panel shows all three channels' min/max for the
inclusive selected interval, even when a curve is hidden. Values use the active
raw/calibrated window and include source sample plus replay/recording time.
Results update on source/selection/mode/smoothing, independently of cursor/zoom.
The pure force_extrema API owns calculation and validation; widgets only display.
