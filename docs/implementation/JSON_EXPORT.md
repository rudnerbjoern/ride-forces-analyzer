# JSON sample exports

[User guide](../user/JSON_EXPORT.md). Ownership:
[arc42 chapter 05](../architecture/05_building_block_view.md#sample-data-export-boundary).

## API and lifecycle

`ride_forces_analyzer.exports.json.export_json(analysis, path, first, last, *, overwrite=False, cancelled, progress)`
accepts a bound `RecordingAnalysis`, a `.json` destination and inclusive source
indices. It returns the exported sample count. It reads prepared sample views
without recalculation, interpolation or rounding. Smoothing uses the full recording;
orientation and context remain the snapshot's independent prepared values.

- Exclusive creation by default. Explicit `overwrite=True` writes to a temporary
  sibling directory, then atomically replaces the destination after successful
  writing/close. Cancellation and serialization/writing/callback/replacement failures
  remove temporary output and preserve the existing destination.
- `TypeError`/`ValueError` identify invalid inputs, snapshot, range, suffix or
  non-JSON values. `FileExistsError` for existing destinations without overwrite
  permission and other filesystem errors propagate.
  `JsonExportCancelled` identifies cooperative cancellation.
- Progress counts collected samples every 250 samples and at the final sample.
  Parallel arrays are collected once, then encoded incrementally. Memory is
  proportional to the selection. Cancellation is checked before creation,
  between samples, between encoder chunks and before completion.
- The shared CSV/JSON worker captures snapshot/range before the file picker,
  pauses playback and asks for replacement confirmation after completing the suffix.
  Declining/closing the question starts no worker; No is the default answer.
  The worker delivers progress/completion on the UI thread and cancels
  on application close. Only success remembers the shared export directory.

## App-shaped format

Replay timestamps use the effective user start marker. Metadata retains original
source indices alongside `effective_ride_bounds`; Analyzer JSON exposes the same
bounds in `recording` and the effective `time.replay_origin`. Original samples and
source marker provenance are unchanged.

Both formats include `calibration`: under app-shaped `metadata` or Analyzer
`analysis`. It retains the versioned recipe, original `source_directions`,
`effective_directions`, inclusive `reference_support` and custom-basis `provenance`
(source hash, algorithm, engine, UTC calculation time and provisional capability).
Without overrides, the effective directions equal the source directions and
custom-reference support/provenance are absent. Source indices remain original.

UTF-8 without BOM, LF, one tab before each root key, one space after its colon,
compact arrays/objects, one root member per line and no trailing newline after
`}`. Root order begins with the app's five numeric arrays:

1. `Vertical Forces (g)`
2. `Lateral Forces (g)`
3. `Longitudinal Forces (g)`
4. `Combined Forces (g)`
5. `Tilt Angle Orientation (degrees)`

The additional parallel arrays are `Timestamp`, `sample_index`,
`recording_seconds`, `replay_seconds`, `raw_x_source`, `raw_y_source`,
`raw_z_source`, `projected_vertical_g`, `projected_lateral_g`,
`projected_longitudinal_g`, `vertical_context`, `capabilities` and `diagnostic_codes`.
All arrays have `last - first + 1` entries in original sample order.

Numeric values and timestamp semantics match the [CSV contract](CSV_EXPORT.md).
Combined is the norm of the smoothed device axes. Missing data is `null`, not zero
or an omitted array position. Non-finite JSON numbers are forbidden. Numeric values
retain calculation precision rather than the source app's two-decimal formatting.
Context uses `VerticalContext.value`; capabilities are objects mapping stage names
to status identifiers; diagnostic codes are arrays of strings per sample.

The final `metadata` object contains:

- `sample_rate_hz`, `sample_rate_origin`, `time_basis`, `smoothing_window_samples`.
- `first_sample`, `last_sample`: exported inclusive interval.
- `source_indices`: canonical `start`, `end`, `gravity`, `incline` source markers.
- `recording`: canonical recording metadata, with absent fields `null`, riding
  position value/origin and source date as its exact numeric token string. No
  epoch or weather-unit conversion is inferred.
- `stages`: algorithm, version and parameter pairs for projection, smoothing,
  independent orientation and context.

This is a sample-data export, not a lossless `.forces` archive or reimport format.
It does not include source paths, unknown source fields, independent GPS sequences
or detected event lists. Custom-calibration provenance includes its source hash.
Recording-level coordinates are not sample GPS
correspondence. Raw units and source-app physical interpretation retain the
[analysis limits](../development/ANALYSIS_MODELS.md#raw-values-and-qualified-quantities).

## Analyzer JSON schema 1

`ride_forces_analyzer.exports.json.export_analyzer_json(analysis, path, first, last, *, overwrite=False, cancelled, progress)`
uses the same validation, bound snapshot, inclusive interval, precision, progress,
encoding, cancellation and atomic overwrite contract as `export_json`. It collects
only measurement/context arrays; repeated timestamp and per-sample quality arrays
are not built. Root members are:

- `schema_version`: integer `1`, independent of the source app's schema version.
- `recording`: canonical metadata/date representation described above, plus
  `indices` containing source markers and `attributes` containing ordered
  `{id, label, value}` entries. Attribute numbers use `{number_token: "…"}` to
  distinguish exact source numeric tokens from strings without precision loss.
  Nested arrays/objects, nulls, booleans and text retain their structure.
- `analysis`: `profile` with name/version/configuration, policy references,
  assumptions and provisional permission; `stages` with projection/smoothing/
  orientation/context recipes; optional `events` recipe; `context_input` and
  `events_input`. `availability` retains state/reason for the four sample stages.
  `units` labels raw axes as unknown, forces as g and orientation as degrees;
  `force_unit_assignment` retains the actual canonical label/evidence state and
  references. Display units do not qualify physical accuracy.
- `time`: `basis`, `sample_rate_hz`, `sample_rate_origin`, `first_sample`,
  `sample_count`, `replay_origin`, `epoch` and time `evidence`. Existing inferred
  time carries no invented epoch. For array offset `i`, source index is
  `first_sample + i`, recording seconds are `index / sample_rate_hz` and replay
  seconds are `(index - replay_origin) / sample_rate_hz`.
- `samples`: groups shown below; every leaf array has `sample_count` entries.
  Missing numeric/stage values are `null`; context identifiers retain their
  prepared meaning, including `unavailable` for invalid rows of an available stage.
- `quality`: shared `capabilities`, common `diagnostics` and `sample_diagnostics`
  keyed by original source-index strings. Diagnostic objects retain code,
  severity, message, channel and source index. Only sample diagnostics within
  the selected interval are included. Apply common diagnostics plus those for
  the requested source index; grouping defines no diagnostic priority.

```text
samples.raw.{x,y,z}
samples.projected.{vertical,lateral,longitudinal}
samples.smoothed.{vertical,lateral,longitudinal,combined}
samples.orientation
samples.vertical_context
```

Combined retains the norm of smoothed device axes, not projected axes. Both JSON
formats read the same prepared sample views and retain the scientific boundaries
above. Analyzer JSON includes no source paths, aligned GPS, detected event lists
or lossless source archive; custom-calibration provenance retains its source hash.
The default filename is `<stem>.analyzer.json`;
the destination suffix remains `.json`. The explorer offers it as a separate
**Data export → Export Analyzer JSON…** action.
