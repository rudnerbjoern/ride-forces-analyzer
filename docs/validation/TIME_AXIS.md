# Explorer time and bounds verification

Current contracts are defined in the [explorer specification](../implementation/RAW_EXPLORER.md).
Time is INFERRED_UNIFORM `index / effective_rate`, independent of GPS. Replay uses
the effective start marker and sample-counter suffix; this does not establish an
acquisition epoch or source end-index inclusion rule.

## Verified behavior

- Source/default rate provenance; 25/50/100 Hz, fractional-rate fallback, final
  sample time, negative replay labels and counter/minute rollover.
- Kraken sample 5510 displays `01:31.47` at 50 Hz, corresponding to 91.94 replay
  seconds. Cursor, ticks, selection and marker labels share the notation.
- Exact sample/seconds round trips (1e-9 sample snapping), inclusive selection,
  one-interval minimum zoom and first/last sample bounds.
- Pointer-anchored wheel zoom (1.25 per notch), time-only drag zoom, full-recording
  zoom-out limit and fixed signed force bounds with 5% padding.
- Default/reset uses source start/end independently, absent boundaries 0/N-1,
  with warnings and no invented source markers. All four presence combinations pass.
- All five originals retain exact plotted time/value pairs, marker positions,
  replacement behavior, bytes/hash/mtime; no source or GPS alignment is performed.
- Calibrated -1/0/+1 g labels remain visible across smoothing and mode changes;
  raw values retain unknown-unit semantics.

## Native Windows evidence

Windows x64 / Python 3.14.6 / Qt 6.12.0; branch `chore/workspace-setup-and-docs`,
base `4b201c42adb8201882bc9c91483ca03124290a57` plus explorer working-tree scope.
Recorded time-contract command `uv run --locked pytest` passed 988 cases in 82.33 s;
`uv run --locked pytest tests/test_reference.py tests/test_explorer.py` passed
49 cases in 8.23 s (`.tmp/reference-final.log`). Ruff lint/format, mypy and Pyright
passed with zero typing errors/warnings. Marker-default coverage also has a
954-case full run in `.tmp/time-final.log`.

These results apply to the recorded time implementation. The broader current
[explorer evidence](RAW_EXPLORER.md) covers later layout/smoothing/reference-label
changes without changing the time contract. Native `.tmp/manta-reference.png`
was inspected for replay-zero, counter ticks, cursor/selection and recording
seconds. Documentation verification uses `npm run test:docs`.
