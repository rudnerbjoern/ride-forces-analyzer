# Export sample data as CSV

Use CSV to inspect your recording in a spreadsheet or another analysis tool.
FFmpeg is not required.

1. Open a `.forces` or `.zforces` recording.
2. Set **From sample** and **To sample** in the inspector's **Selection** section.
   Both endpoints are included. The initial selection includes the whole recording.
3. Choose the desired **Smoothing** setting and wait for the chart to finish updating.
4. Choose **Data export → Export CSV…**, choose a new filename and save.

The export runs in the background with a progress window and **Cancel** button.
If the destination exists, confirm replacement or decline to keep the existing
file. Replacement happens only after a successful export; cancellation or failure
preserves the previous file. Cancelling or closing the application removes
incomplete output. The original recording stays unchanged. The app remembers the folder after a successful export and also uses it for
video exports.

## What the file contains

- One row per selected sample, with its original index and recording/replay time
  in seconds. Negative replay times identify samples before the start marker.
- `Timestamp` shows replay time in the app's `MM:SS.ff` format. At 50 Hz, `ff`
  counts samples from 00 to 49. Fractional sample rates use explicit seconds.
- Original x/y/z measurements, calculated directional forces and those forces
  with your chosen smoothing. Samples outside the selection can contribute to
  smoothing near its edges.
- Combined force magnitude, calculated from the smoothed device x/y/z values.
- Tilt and vertical airtime labels, where available.
- Sample rate, smoothing and additional timing/status codes that help other
  tools identify unavailable values and calculation limits.

The CSV includes all available channels, independently of hidden curves or the
raw/calibrated display toggle. Unavailable calculated values leave empty cells; measured zeroes appear as
numbers. GPS positions and ride/weather metadata are not sample columns.
Force interpretations and airtime labels remain provisional; original device axes
have unknown units. See [forces and airtime](FORCES_AND_AIRTIME.md).

## Open in a spreadsheet

The file uses UTF-8, **commas as column separators** and **decimal points**,
independently of the application language. If your spreadsheet does not separate
columns automatically, use its text/CSV import and select these settings.
Column names and airtime labels use English, even when the app uses another language.
The first six columns use the Ride Forces app's names and order, including
`Timestamp`. Our additional data follows these columns; numeric recording/replay
seconds are also retained. Force values can have more decimal places than the numbers shown in the app.

[Explore a recording](EXPLORER.md) · [Forces and airtime](FORCES_AND_AIRTIME.md)
