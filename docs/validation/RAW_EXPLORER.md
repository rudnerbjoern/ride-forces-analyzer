# Explorer verification

Verified behavior follows the [explorer contract](../implementation/RAW_EXPLORER.md).
M4 remains partial because the persistent ride library and full milestone
acceptance are outstanding.

## Covered behavior

- All five originals: complete plotted values, source integrity and raw/calibrated fallback.
- Background loading, error recovery, replacement and safe close during loading.
- Sample navigation, inclusive/visible-range selection, source markers and extrema.
- Bounded time-only wheel/drag zoom, marker-based reset and independent absent bounds.
- Live odd-window smoothing/reset, fixed force bounds and -1/0/+1 g references.
- Literal metadata, directional value cards, diagnostics and unknown-unit raw labels.
- Wide/compact layouts, scroll access, native caption and application name without repetition.
- Independent GPS availability, gap-preserving geometry and dialog lifecycle.
- Light/dark palettes preserve data, viewport, selection and export colors.

Time is inferred index/rate, independent of GPS. Replay uses start-relative
`MM:SS.ff`; at 50 Hz Kraken sample 5510 displays `01:31.47` (91.94 s).
Fractional rates use explicit seconds. Marker defaults never synthesize source
markers. Source end-index semantics and acquisition epochs remain unqualified.

## Scoped evidence

Native Windows x64, Python 3.14.6 / Qt 6.12.0.
Explorer acceptance uses its Windows test scope on
`chore/workspace-setup-and-docs`, base
`4b201c42adb8201882bc9c91483ca03124290a57`; appearance/localization checks use
`feat/4k-force-exports`, base `d88304e25dc67b9c0cec6ffe9c55f03d4d74e66b`.

`uv run --locked pytest tests/test_explorer.py tests/test_gui.py tests/test_explorer_gui.py`
passed in the recorded explorer scope. Appearance checks cover
`tests/test_theme_gui.py`, startup at 100%/200% scaling and light text/channel/
marker contrast of at least 4.5:1 against white. Changed-file Ruff, mypy and
Pyright checks passed. Native wide/compact captures were inspected.
[Localization verification](LOCALIZATION.md) records current text-fit checks.

Results apply to those tested contents. Clean-machine release, platform-dependent
caption colors and universal responsiveness guarantees are not established.
GPS is coarse reference only; no background map or confirmed speed-color contract.
