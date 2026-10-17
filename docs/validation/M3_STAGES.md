# M3 model and device validation

Reduced M3 is complete; see [current acceptance](M3.md). Models and explicit device/unit primitives are implemented;
[frame validation](M3_STAGE3.md) and [source-app comparison](APP_REFERENCE.md)
cover their separate contracts. Complete scientific acceptance remains open under
the [M3 plan](../implementation/DEV-REQ-003/PLAN.md).

## Input and source preservation

Native Windows / Python 3.14.6; prerequisite revision
`0db96029c724edccb8175c7843bf8f18be3b808d`.
`uv run --locked pytest tests/test_import_service.py tests/test_fixture_inventory.py tests/test_project.py tests/test_recording_models.py tests/test_source_models.py tests/test_import_results.py`
passed **131 tests in 17.31 s**. All five originals retain bytes, pinned size/hash
and modification time. Timestamp ordering does not assign GPS units or epochs.

## Immutable model evidence

Native Windows / Python 3.14.6 / NumPy 2.5.4, prerequisite revision above plus
model working-tree scope. The final model suite includes 30 cases; array ownership,
missingness, provenance, capabilities and offline construction are covered.

| Command                                                                                                     | Actual result                                                                     |
| ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `uv lock --check`                                                                                           | Consistent unchanged root lock; 32 packages                                       |
| `uv run --locked pytest tests/test_import_service.py tests/test_project.py`                                 | M2 prerequisite: 61 passed in 14.42 s before model coding                         |
| `uv lock --project .tmp/m3-stage1-audit --python 3.14.6`                                                    | Separate exact-version audit lock: 13 packages                                    |
| `uv sync --project .tmp/m3-stage1-audit --python 3.14.6 --locked --no-build`                                | 12 distributions installed from wheels in the isolated audit environment          |
| `.tmp/m3-stage1-audit/.venv/Scripts/python.exe .tmp/m3-stage1-audit-smoke.py`                               | 8 synthetic upstream API checks passed; no original recording interpretation      |
| `uv run --locked pytest -o cache_dir=.tmp/pytest-cache tests/test_analysis_models.py`                       | 29 focused cases passed before adding the final offline case                      |
| `uv run --locked pytest -o cache_dir=.tmp/pytest-cache tests/test_analysis_models.py -k model_construction` | New final offline case: 1 passed, 29 deselected                                   |
| `uv run --locked ruff check .`                                                                              | Passed for final code                                                             |
| `uv run --locked ruff format --check src tests`                                                             | 39 files formatted; passed                                                        |
| `uv run --locked mypy src`                                                                                  | No issues in 23 source files; reused after later test/documentation-only edits    |
| `npm run typecheck`                                                                                         | 0 errors/warnings for final source and tests                                      |
| `npm run test:types`                                                                                        | 11 passed                                                                         |
| `npm run test:dependencies`                                                                                 | 15 passed                                                                         |
| `node --test tests/ci/changes.test.mjs`                                                                     | 40 passed                                                                         |
| `uv run --locked pytest -o cache_dir=.tmp/pytest-cache`                                                     | 866 passed in 39.13 s, including all 30 analysis cases and native GUI regressions |
| `.tmp/node-v26.11.1-win-x64/node.exe .tmp/validate-arc42.mjs`                                               | All 7 definitions passed; no visual rendering verification                        |

## Explicit device/unit evidence

Native Windows / Python 3.14.6 / NumPy 2.5.4 / Pint 0.26.1; device/model scope.

| Command                                                                                                             | Actual result                                                                                   |
| ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `uv add --optional analysis pint==0.26.1 --no-sync`                                                                 | Required manifest/lock adoption; 36 packages resolved, existing versions retained               |
| `uv sync --locked --all-extras --group dev --no-build`                                                              | Pint and three new transitive distributions installed; local editable project rebuilt           |
| `uv run --locked pytest -o cache_dir=.tmp/pytest-cache tests/test_device_analysis.py tests/test_analysis_models.py` | 59 passed in 6.15 s; 29 device and 30 model cases                                               |
| `uv lock --check`                                                                                                   | Consistent lock; 36 packages                                                                    |
| `uv run --locked ruff check .`                                                                                      | Passed                                                                                          |
| `uv run --locked ruff format --check src tests`                                                                     | Passed; 41 files already formatted                                                              |
| `uv run --locked mypy src`                                                                                          | No issues in 24 source files; source unchanged after this result                                |
| `npm run typecheck`                                                                                                 | 0 errors/warnings for final source/tests                                                        |
| `npm run test:types`                                                                                                | 11 passed                                                                                       |
| `npm run test:dependencies`                                                                                         | 15 passed                                                                                       |
| `node --test tests/ci/changes.test.mjs`                                                                             | 40 passed                                                                                       |
| `uv run --locked pytest -o cache_dir=.tmp/pytest-cache`                                                             | 895 passed in 41.31 s, including device/model, M2, integrity and native GUI tests               |
| `npm run test:docs`                                                                                                 | 52 local-link tests passed; Markdownlint 52 files / 0 issues; CSpell 114 files / 0 issues       |
| `.tmp/node-v26.11.1-win-x64/node.exe .tmp/validate-arc42.mjs`                                                       | 8 Mermaid definitions passed syntax checks; visual layout/hosted rendering unverified           |
| `uv run --locked python .tmp/inspect-m3-evidence.py`                                                                | All five pinned byte lengths, SHA-256 digests and Stage 0 baseline modification times unchanged |

## Qualification limits

The device-only API requires caller-attested, source-bound unit/quantity contracts;
no real fixture is automatically assigned SI units or a physical norm by that API.
Original Watch gravity/GPS remain absent. SCI-004–006/010–012 and VAL-001/004 have
device-scoped evidence; AC-04/06 and complete ARC-004 remain partial. Model/device
checks do not establish general rider calibration, GPS geodesics or physical time.
App-reference g display is a separate adopted contract with per-source evidence.
Temporary artifacts stay in `.tmp/`; no hosted CI result is implied.

Current acceptance is defined by the [reduced M3 requirements](../requirements/DEV-REQ-003-scientific-analysis.md)
and [plan](../implementation/DEV-REQ-003/PLAN.md). This report verifies its recorded
API scope; it does not establish planned extrema or final reduced-M3 acceptance.
General physical qualification and GPS analytics are not completion prerequisites.
