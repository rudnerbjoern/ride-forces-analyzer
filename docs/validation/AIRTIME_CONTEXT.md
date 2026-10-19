# Airtime context and layout validation

## Tested scope

Native Windows desktop, repository root, 2026-10-19. Working tree on
`feat/column-lateral-timeline`, based on
`65a973261a59cf290f1a3621079ae7da5c2bf6df`, including the airtime source,
tests, configuration, documentation and generated reference images.
This is local working-tree evidence, not a hosted CI result. The full-run source
scope is now committed as `b055fcb`; the adaptive-height adjustment below is
validated separately on top of that commit.

Scope includes source-time airtime classification and context stabilization,
localized labels and shared colors, the explorer context strip and current-value
card, zoom/visibility/theme behavior, left-to-right Column lateral history and
signed longitudinal rendering across the export themes. Original recording
integrity is covered by the full application suite.

## Environment and preparation

- Native Windows Python 3.14.6 and uv 0.13.0.
- Node 26.11.1 and bundled npm 11.20.0 from `.tmp/node-v26.11.1-win-x64`.
  This directory was prepended to PATH only for the validation process.
- Locked Node tools installed with
  `npm ci --no-audit --no-fund --cache .tmp/npm-cache`.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File setup.ps1 -VideoExport`
  synchronized the locked Python environment and installed checksum-verified
  FFmpeg 9.0.2 under `.tmp/ffmpeg/bin`. Native encoding tests were enabled.

## Results

| Check          | Command                                                                    | Result                                    |
| -------------- | -------------------------------------------------------------------------- | ----------------------------------------- |
| Lockfile       | `uv lock --check`                                                          | 44 packages resolved; valid               |
| Lint           | `uv run --locked ruff check .`                                             | Passed                                    |
| Formatting     | `uv run --locked ruff format --check src tests`                            | 132 files formatted                       |
| mypy           | `uv run --locked mypy src`                                                 | 67 source files; no issues                |
| Pyright        | `npm run typecheck`                                                        | 0 errors, 0 warnings                      |
| Type contracts | `npm run test:types`                                                       | 11 passed                                 |
| Dependencies   | `npm run test:dependencies`                                                | 20 passed                                 |
| CI routing     | `node --test tests/ci/changes.test.mjs`                                    | 45 passed                                 |
| Application    | `uv run --locked pytest -q -ra --junitxml=.tmp/full-validation-pytest.xml` | 1,539 passed; 0 skipped; 249.44 s         |
| Documentation  | `npm run test:docs`                                                        | Markdown, spelling and local links passed |

The complete application suite passed, including native GUI, recording integrity,
real video encoding/decoding and cancellation coverage. No Python tests were
skipped. The separate delivery-skill regression suite was not run because its
implementation and dependencies were not changed.

Final documentation checks include this report and the updated airtime contract.
Actual runner output and JUnit evidence are retained in
`.tmp/full-validation-*.log`, `.tmp/full-validation-results.json`,
`.tmp/full-validation-pytest.xml` and `.tmp/documentation-tests.log`.

## Adaptive workspace height

Native Windows, `b055fcb` plus the current `ui/window.py` sizing adjustment,
`tests/ui/test_explorer.py` regression and accompanying documentation/screenshots.
The chart ignores its old preferred height while retaining its explicit readable
minimum; controls are not hidden and scrollbar policies are not forced off.

```powershell
.venv/Scripts/python.exe -m pytest tests/ui/test_explorer.py::test_chart_shrinks_to_available_height_without_workspace_scrolling tests/ui/test_explorer.py::test_focus_workspace_layout_and_current_value_cards tests/ui/test_explorer.py::test_vertical_context_bar_preserves_curve_and_tracks_viewport -q
.venv/Scripts/python.exe -m ruff check src/ride_forces_analyzer/ui/window.py tests/ui/test_explorer.py
.venv/Scripts/python.exe -m ruff format --check src/ride_forces_analyzer/ui/window.py tests/ui/test_explorer.py
.venv/Scripts/python.exe -m mypy src/ride_forces_analyzer/ui/window.py
.tmp/node-v26.11.1-win-x64/node.exe node_modules/pyright/index.js src/ride_forces_analyzer/ui/window.py tests/ui/test_explorer.py
npm run test:docs
```

Seven GUI cases passed in 17.27 s. Both languages and appearances fit without
chart scrolling at 1600×1100, 1280×820 and 1280×720, including shrink/grow cycles;
controls/value cards remain visible and data/time range/sample remain unchanged.
Existing compact-window and context-strip regressions pass. Ruff, formatting,
strict mypy and Pyright passed. Updated native screenshots show the regular
layout without changing its scroll position. Very small 720×480 windows retain
scrolling to keep controls reachable. The full application suite was not repeated
for this isolated sizing adjustment; its acceptance is limited to these checks.

## Reproducible application screenshots

Native Windows, `b055fcb` plus the adaptive workspace changes and
`scripts/capture_app_reference.py`, `tests/ui/test_reference_screenshots.py` and
the accompanying image documentation. The script fixes the Voltron source hash,
sample, selection, smoothing, language, font, scaling and export settings, using
isolated temporary preferences and the actual application widgets.

```powershell
.venv/Scripts/python.exe -m pytest tests/ui/test_reference_screenshots.py -q
.venv/Scripts/python.exe scripts/capture_app_reference.py
.venv/Scripts/python.exe -m ruff check scripts/capture_app_reference.py tests/ui/test_reference_screenshots.py
.venv/Scripts/python.exe -m ruff format --check scripts/capture_app_reference.py tests/ui/test_reference_screenshots.py
.venv/Scripts/python.exe -m mypy src scripts/capture_app_reference.py
.tmp/node-v26.11.1-win-x64/node.exe node_modules/pyright/index.js scripts/capture_app_reference.py tests/ui/test_reference_screenshots.py
npm run test:docs
```

Both focused tests passed: repeated captures have identical pixels, personal
preferences and original recording bytes remain unchanged, and a modified source
is rejected before image creation. The three documentation screenshots and their
settings manifest were generated successfully. Ruff, formatting, mypy (68 files),
Pyright and documentation checks passed. This verifies repeatability within the
tested Windows/Qt environment; other Windows, Qt or font versions may differ.
Runner output is retained in `.tmp/app-reference-*.log` and
`.tmp/documentation-tests.log`.

## Limits

The [airtime thresholds](../implementation/AIRTIME.md) remain provisional
presentation heuristics; passing tests do not establish scientific rider-load
qualification. GPU preference cases can use the supported CPU fallback and do not
qualify every GPU/driver. Installed Windows tests do not establish clean-machine
release qualification. Hosted CI and exact-commit merge gates remain separate.
No staging, commit, push or publication was performed by this validation.
