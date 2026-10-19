# Airtime context and layout validation

## Tested scope

Native Windows desktop, repository root, 2026-10-19. Working tree on
`feat/column-lateral-timeline`, based on
`65a973261a59cf290f1a3621079ae7da5c2bf6df`, including the current source,
tests, configuration, documentation and generated reference images.
This is local working-tree evidence, not a committed revision or hosted CI result.

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

## Limits

The [airtime thresholds](../implementation/AIRTIME.md) remain provisional
presentation heuristics; passing tests do not establish scientific rider-load
qualification. GPU preference cases can use the supported CPU fallback and do not
qualify every GPU/driver. Installed Windows tests do not establish clean-machine
release qualification. Hosted CI and exact-commit merge gates remain separate.
No staging, commit, push or publication was performed by this validation.
