# Export sample data as CSV

Use CSV to inspect your recording in a spreadsheet or another analysis tool.
FFmpeg is not required.

1. Open a `.forces` recording.
2. Set **From sample** and **To sample** in the inspector's **Selection** section.
   Both endpoints are included. The initial selection includes the whole recording.
3. Choose the desired **Smoothing** setting and wait for the chart to finish updating.
4. Choose **Data export → Export CSV…**, choose a new filename and save.

The export runs in the background with a progress window and **Cancel** button.
If the destination exists, confirm replacement or decline to keep the existing
file. Replacement happens only after a successful export; cancellation or failure
preserves the previous file. Cancelling or closing the application removes
incomplete output. The original recording stays unchanged. Successful exports
remember their destination folder,
shared with video export.

## What the file contains

- One row per selected sample, with its original index and recording/replay time
  in seconds. Negative replay times identify samples before the start marker.
- `Timestamp` shows replay time in the app's `MM:SS.ff` format. At 50 Hz, `ff`
  counts samples from 00 to 49. Fractional sample rates use explicit seconds.
- Original x/y/z values, projected forces and forces with the current smoothing.
  Smoothing uses the complete recording before selecting the export interval.
- Combined force magnitude, calculated from the smoothed device x/y/z values.
- Available tilt and the prepared vertical airtime context.
- Sample rate, time basis, smoothing window and scientific status/diagnostic codes
  to identify the meaning and quality of the values.

The CSV includes all available channels, independently of hidden curves or the
raw/calibrated display toggle. Missing derived values remain empty; zero remains
a numeric value. GPS positions and ride/weather metadata are not sample columns.
Force interpretations and airtime labels remain provisional; original device axes
have unknown units. See [forces and airtime](FORCES_AND_AIRTIME.md).

## Open in a spreadsheet

The file uses UTF-8, **commas as column separators** and **decimal points**,
independently of the application language. If your spreadsheet does not separate
columns automatically, use its text/CSV import and select these settings.
Column names and context identifiers are stable English names.
The first six columns use the Ride Forces app's names and order, including
`Timestamp`. Our additional data follows these columns; numeric recording/replay
seconds are also retained. Force values preserve our calculation precision.

[Explore a recording](EXPLORER.md) · [CSV format](../implementation/CSV_EXPORT.md)
