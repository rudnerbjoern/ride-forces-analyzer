# Export sample data as JSON

Use JSON to process a recording in scripts or other analysis tools. FFmpeg is
not required.

1. Open a `.forces` or `.zforces` recording.
2. Set **From sample** and **To sample**; both endpoints are included.
3. Choose **Smoothing** and wait for the analysis to finish updating.
4. Choose **Data export → Export JSON…** or **Export Analyzer JSON…** and choose
   a new filename.

The progress window offers **Cancel**. Existing destinations require confirmation
before replacement. Declining, cancelling or a failed export preserves the previous
file; replacement happens only after a successful export. Cancelling or closing
the application removes incomplete output. Successful exports remember
the destination folder, shared with CSV and video export.

## Choose a format

- **Export JSON…** follows the Ride Forces app's array names and order, with our
  additional sample data and metadata.
- **Export Analyzer JSON…** uses our versioned, structured format for analysis
  scripts. It groups related arrays and stores shared time/quality information
  once, reducing repetition. The suggested filename ends in `.analyzer.json`.

Both options export the same prepared measurements and context. Use the app-shaped
option when its field names are needed; use Analyzer JSON for a more compact data
structure with explicit calculation settings and scientific limitations.

## App-shaped JSON contents

The first five arrays follow the Ride Forces app's JSON export: vertical, lateral,
longitudinal and combined forces, followed by tilt angle. Each position in an
array refers to the same sample in the other arrays.

Additional arrays contain timestamps, original sample indices, recording/replay
seconds, raw x/y/z values, projected forces, airtime context and quality information.
The `metadata` object records the selected interval, sample rate, smoothing,
analysis settings, source markers and available ride/weather metadata.
Recording dates retain their original numeric text without assuming an epoch.

The export uses the current analysis snapshot, including full-recording smoothing,
regardless of hidden chart curves or the raw/calibrated display toggle. Values
retain our calculation precision; they are not rounded to the app's two decimals.
Matching names and structure do not imply identical numerical results.

## Analyzer JSON contents

The document groups recording information, analysis settings, time, sample arrays
and quality information. Recording information includes available train, row and
seat attributes, source markers and weather metadata. Source numeric attribute
tokens are retained explicitly, without guessing their meaning or units.

Raw axes, projected/smoothed forces, Combined, orientation and airtime context
remain parallel arrays: the same position refers to the same source sample.
The file stores the first sample, number of samples, sample rate and replay origin
once. Scripts can derive recording/replay seconds from these values.

Shared quality status and general diagnostics occur once. Diagnostics for individual
samples use their original sample indices. A schema version identifies the format.
Analyzer JSON is a data export; importing it as a recording is not supported.

Missing values are `null`; zero remains a number. Field names and context identifiers
are English, independently of the application language. The file is UTF-8 with
compact arrays, like the app export.

GPS samples are not assigned to force samples. Available recording-level location
metadata stays recording-level. Derived forces and airtime interpretations remain
provisional; raw device axes have unknown units.

[Explore a recording](EXPLORER.md) · [Forces and airtime](FORCES_AND_AIRTIME.md) ·
[JSON format](../implementation/JSON_EXPORT.md)
