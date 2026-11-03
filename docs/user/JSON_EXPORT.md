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

- **Export JSON…** uses the Ride Forces app's familiar field names, with additional
  sample data and recording information.
- **Export Analyzer JSON…** organizes the same measurements for further analysis,
  with less repeated information. Its suggested filename ends in `.analyzer.json`.

Choose the first option if your analysis tool expects the Ride Forces field names.
Choose Analyzer JSON for a more compact file. Neither option can be imported back
as a recording.

## What is included

Both formats include:

- Vertical, lateral, longitudinal and Combined forces, plus tilt where available.
- Original x/y/z measurements and calculated forces before and after smoothing.
- Airtime labels, original sample numbers and timing information.
- Your selected interval, sample rate, smoothing and marker settings.
- Available ride, park, row, seat, train and weather information, with your saved
  Library edits.
- Status information explaining missing values and calculation limits.

The export includes available channels even if their chart curves are hidden.
Switching the chart to raw view does not remove calculated forces from the export.
Your chosen smoothing applies; samples outside the selection can contribute near
its edges. Values can have more decimal places than those shown in either app,
so matching field names do not promise identical numbers.

## Using the file

Each measurement is stored as a list of values. Matching positions in the lists
refer to the same sample. Analyzer JSON groups related lists and stores common
timing information once, rather than repeating it for every sample.

Missing values are written as `null`; measured zeroes remain numbers. Field names
and airtime labels use English, regardless of the app's language. The file uses
UTF-8 text.

Dates are kept as their original source values, rather than converted to the
readable dates shown in the Library. GPS route points are not matched to force
samples or included as a route. Calculated forces and airtime labels have the same
limits as the charts; see [forces and airtime](FORCES_AND_AIRTIME.md).

[Explore a recording](EXPLORER.md) · [CSV export](CSV_EXPORT.md)
