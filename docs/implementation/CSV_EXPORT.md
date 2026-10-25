# CSV sample export

[User guide](../user/CSV_EXPORT.md). Component ownership belongs to
[arc42 chapter 05](../architecture/05_building_block_view.md#sample-data-export-boundary).

## API and lifecycle

`ride_forces_analyzer.exports.csv.export_csv(analysis, path, first, last, *, overwrite=False, cancelled, progress)`
accepts a bound `RecordingAnalysis`, a `.csv` destination and inclusive source indices.
It returns the number of written data rows. The serializer validates the snapshot,
reads `analysis.sample(index)` and never prepares or interpolates measurements.
Full-history smoothing/context and independent orientation remain bound to the
snapshot's existing configuration, regardless of workspace display mode or later updates.

- UTF-8 with BOM, comma delimiter, standard CSV quoting, decimal points and stable
  English headers/identifiers. Output is independent of UI language.
- Raw-capable snapshots are supported. Missing derived stages/rows produce empty
  fields; valid zero is retained. No artificial values, GPS alignment or unit qualification.
- Exclusive destination creation by default. Explicit `overwrite=True` writes to a
  temporary sibling directory and atomically replaces the destination only after
  successful writing/close. Cancellation and writing/callback/replacement failures
  remove temporary output and preserve the existing destination.
- Progress reports written row counts every 250 samples and at the final row.
  Cancellation is checked before writing, between samples and before completion.
- Invalid indices/suffix/snapshots raise `TypeError` or `ValueError`; existing
  destinations without overwrite permission raise `FileExistsError`; filesystem
  errors propagate as `OSError`.
  `CsvExportCancelled` identifies cooperative cancellation.
- The explorer captures its snapshot and From/To interval before the save dialog,
  pauses playback and asks for replacement confirmation after completing the suffix.
  Declining/closing the question starts no worker; No is the default answer.
  A confirmed export starts a Qt worker. Progress/cancellation and completion/errors
  return on the UI thread. Closing the main window requests cancellation.
- Successful completion remembers the existing shared export directory. Failure
  or cancellation preserves it.

## Columns

| Columns                                                                   | Meaning                                                                            |
| ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `Timestamp`                                                               | Start-marker-relative replay label; `MM:SS.ff` at integer sample rates             |
| `sample_index`                                                            | Original zero-based force sample index                                             |
| `recording_seconds`, `replay_seconds`                                     | Index/rate and (index − start marker)/rate; no epoch                               |
| `raw_x_source`, `raw_y_source`, `raw_z_source`                            | Original device axes, unknown units                                                |
| `projected_vertical_g`, `projected_lateral_g`, `projected_longitudinal_g` | Unfiltered source-app projection                                                   |
| `Vertical Forces (g)`, `Lateral Forces (g)`, `Longitudinal Forces (g)`    | Prepared centered-mean values at the snapshot's smoothing window                   |
| `Combined Forces (g)`                                                     | Norm of centered-mean device x/y/z values, before directional projection           |
| `Tilt Angle Orientation (degrees)`                                        | Independent source-gravity tilt, empty for absent/invalid correspondence           |
| `vertical_context`                                                        | Prepared provisional `VerticalContext.value`, empty when unavailable               |
| `sample_rate_hz`, `time_basis`                                            | Effective source/default rate and declared time-basis identifier                   |
| `smoothing_window_samples`                                                | Effective window; 1 disables smoothing                                             |
| `capabilities`                                                            | Semicolon-separated `stage=status` pairs, retaining provisional/unavailable states |
| `diagnostic_codes`                                                        | Semicolon-separated global/current-sample analysis diagnostic codes                |

Derived force columns follow the adopted source-app policy: vertical positive
seat pressure, lateral positive right, longitudinal positive acceleration.
Their g interpretation remains provisional, as retained by the capability fields.
Missingness and scientific limits follow the [analysis contracts](../development/ANALYSIS_MODELS.md#raw-values-and-qualified-quantities).
The first six columns match the source app's headers and order: `Timestamp`, the
three directional forces, Combined and tilt. Additional columns follow them.
`Timestamp` uses the existing replay formatter: at integer rates, `ff` is a sample
counter (00–49 at 50 Hz); negative offsets retain their sign. Fractional rates use
explicit seconds to three decimal places, as in the explorer. Time remains relative
to the source start marker, even for a smaller export selection. Numeric recording
and replay seconds remain available separately. Force values retain our full
precision and documented calculation policy; matching headers do not imply
identical rounding or source-app numerical results.
Combined shares the smoothing stage's availability and provisional g interpretation.
It uses the same full-history window and shortened recording edges, without
averaging magnitudes or taking the norm of projected force components.
No GPS, ride/weather metadata or event-list export is included in this sample table.
