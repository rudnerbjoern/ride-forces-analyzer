# Explorer validation

The implemented [explorer contracts](../implementation/RAW_EXPLORER.md) are locally
verified within the scope below. Reduced M3 is complete with [focused acceptance](M3.md); M4 library acceptance
remains open. Current behavior is described in the contracts and [README](../../README.md),
not by superseded implementation steps.

## Verified scope

- All five complete originals: plotted values/time coordinates, calibrated/raw
  switching, source integrity (bytes, pinned length/SHA-256 and modification time).
- Background imports, timer responsiveness, cancelled/malformed/failed input,
  valid recording replacement and safe close during loading.
- Sample navigation, inclusive/visible-range selection, bounded wheel/drag zoom,
  marker-based reset, absent boundaries, source markers and axis visibility.
- Live odd-window smoothing, right-click reset, -1/0/+1 g labels and fixed force
  bounds; slider backgrounds remain dark in enabled/disabled states.
- Plain-text metadata including literal markup, absent fields, duplicate attributes,
  directional current-value cards and raw unknown-unit labels.
- Focus workspace at 1280×820, custom 720×480, resize 800×500, compact Inspector,
  scrollable fields, expandable details and direct diagnostic access.
- GPS availability, route geometry and dialog lifecycle; native caption icon,
  recording-specific title and no duplicate toolbar application name.

## Runner evidence

Native Windows x64 / Python 3.14.6 / PySide6 6.12.0; locked environment.
Tested working tree: `chore/workspace-setup-and-docs`, base
`4b201c42adb8201882bc9c91483ca03124290a57`. Scope: config defaults, explorer/GPS
presentation, ui modules and associated settings/explorer/GUI tests.
Commands run from repository root; logs/captures are ignored `.tmp/` artifacts.

| Command / scope                                                                                                                                                                                                                                                                                  | Actual result                                                                  | Runner log                      |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ | ------------------------------- |
| `uv run --locked pytest` — focus workspace and scientific/import regressions                                                                                                                                                                                                                     | 1,040 passed, 85.07 s                                                          | `.tmp/focus-final.log`          |
| `uv run --locked pytest tests/test_gui.py tests/test_explorer_gui.py::test_focus_workspace_layout_and_current_value_cards tests/test_explorer_gui.py::test_smoothing_slider_preserves_source_time_and_selection tests/test_explorer_gui.py::test_focus_header_preserves_literal_device_metadata` | 5 passed, 8.34 s                                                               | `.tmp/focus-final-affected.log` |
| `uv run --locked pytest tests/test_gui.py tests/test_explorer_gui.py::test_focus_workspace_layout_and_current_value_cards tests/test_explorer_gui.py::test_smoothing_slider_preserves_source_time_and_selection tests/test_explorer_gui.py::test_slider_background_stays_dark`                   | 5 passed, 9.34 s                                                               | `.tmp/slider-style.log`         |
| `uv run --locked pytest tests/test_gui.py tests/test_explorer_gui.py::test_focus_workspace_layout_and_current_value_cards tests/test_explorer_gui.py::test_smoothing_slider_preserves_source_time_and_selection tests/test_explorer_gui.py::test_open_chart_navigation_selection_and_integrity`  | 9 passed, 13.60 s                                                              | `.tmp/caption-style.log`        |
| `uv run --locked pytest tests/test_gui.py` — current toolbar/title                                                                                                                                                                                                                               | 2 passed, 3.16 s                                                               | `.tmp/toolbar-identity.log`     |
| `uv run --locked ruff check .`; `uv run --locked ruff format --check src tests`; `uv run --locked mypy src`; `npm run typecheck`                                                                                                                                                                 | Passed; final 55 formatted files, 33 source files, zero typing errors/warnings | `.tmp/toolbar-identity.log`     |
| `uv lock --check`; `npm run test:types`; `npm run test:dependencies`                                                                                                                                                                                                                             | 37 packages; 11 passed; 15 passed                                              | `.tmp/focus-quality.log`        |

The full-suite result applies to its tested content; affected suites cover the
subsequent plain-text header, slider style, caption and toolbar changes. Unaffected
results are reused for unchanged executable inputs. These are local results, not
hosted CI. This documentation review changes no executable inputs or acceptance.

`.venv/Scripts/python.exe .tmp/capture-focus.py` and
`.venv/Scripts/python.exe .tmp/capture-caption.py` produced inspected native captures
in `.tmp/focus-workspace.png`, `.tmp/focus-compact.png` and `.tmp/caption-workspace.png`.
The native dark-caption attribute was accepted. Optional Windows 11 caption/text/
border colors were rejected by this environment; their exact colors remain unverified.

## Startup geometry verification

On PR #12 base `77588f4fb3be28706db6fb61458cd5766aa85a72` plus
`tests/test_gui.py`, native Windows command
`.venv/Scripts/python.exe -m pytest tests/test_gui.py -v -s` passed all four
startup cases in 5.05 s (`.tmp/pr12-gui.log`). Default/custom settings run at Qt
scale factors 1 and 2. Requested client size is exact before show; after show,
reductions are accepted only in dimensions where the requested size plus native
frame exceeds the available desktop. Other dimensions must remain exact.
Assertions include actual/requested geometry and desktop/frame bounds.
Ruff check, Ruff format check and Pyright on `tests/test_gui.py` also passed.
The reported hosted default-size failure motivates this portable assertion;
the original runner's actual geometry was not included in its failure output.
The constrained local desktop retained the requested size, which is also valid.
Application code and dependencies are unchanged; prior unaffected evidence is
reused. No additional full run was performed; hosted success remains open.

## Limits

Tests simulate the file-picker result; manual picker navigation is not claimed.
Compact windows scroll rather than show every field simultaneously. No universal
latency guarantee exists for arbitrary input size; non-finite display bounds fail
without replacing the previous usable recording. Clean-machine release/ARM64,
physical calibration and private source-app algorithm identity remain unverified.
[Time contracts](TIME_AXIS.md) and [source comparisons](APP_REFERENCE.md) retain
numeric limits and known discrepancies. No Git delivery is part of these results.
