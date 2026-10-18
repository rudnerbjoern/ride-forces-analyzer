# Focused test runtime

Scope: representative GUI cases, service import coverage and small renderer test
frames used only by dialog/palette/language interaction tests. Production code,
original recordings and CI gates are unchanged.

Native Windows, Python 3.14.6, repository root, base `499629e` plus the test changes.
Timing commands below retain the filenames used when measured; current subsystem
paths are listed in [code quality](../development/CODE_QUALITY.md#test-coverage):

```powershell
.venv/Scripts/python.exe -m pytest tests/test_explorer_gui.py tests/test_export_gui.py tests/test_import_service.py tests/test_theme_gui.py tests/test_i18n_gui.py --junitxml=.tmp/test-runtime-after.xml
```

The final focused run passed: **90 tests in 67.42 s**, compared with
**113 tests in 117.06 s** before the changes on the same machine (42% less time).

| Affected file group |   Before |   After |
| :------------------ | -------: | ------: |
| Explorer GUI        |  44.25 s | 25.78 s |
| Export GUI          |  36.56 s | 19.41 s |
| Import service      |  12.36 s |  4.68 s |
| Theme GUI           |   7.59 s |  6.45 s |
| Localization GUI    |  13.86 s | 10.39 s |

Rows sum JUnit case durations; overall pytest time also includes collection.
Additional focused checks passed:

```powershell
.venv/Scripts/ruff.exe check tests
.venv/Scripts/ruff.exe format --check tests
.tmp/node-v26.11.1-win-x64/node.exe node_modules/pyright/index.js
.venv/Scripts/python.exe -m pytest tests/test_export_preview.py tests/test_i18n.py tests/test_rendering.py tests/test_project.py -k "not native_encoder and not cancel_during_real_encoding and not decoder_rejects" --junitxml=.tmp/test-runtime-rendering.xml
```

Ruff check/format passed; strict Pyright reported zero errors/warnings.
Real-frame previews, layout geometry/directions/alpha, localization and original
fixture integrity: **363 passed in 40.82 s**. The 10 native encoder/output-decoder
cases were excluded because encoding code and contracts are unchanged.
The focused timing comparison does not establish a GitHub job duration.

## Subsystem organization verification

Native Windows, same base plus the test-directory changes. Before/after
`python -m pytest --collect-only -q` lists match after path mapping: **1,496
identical test cases**, with no added, missing or duplicated cases.

```powershell
.venv/Scripts/python.exe -m pytest tests/domain tests/importers tests/analysis tests/recordings tests/packaging tests/tooling tests/rendering/test_preview.py tests/rendering/test_reference_script.py tests/ui/test_export.py tests/ui/test_localization.py --junitxml=.tmp/test-sort-results.xml
.venv/Scripts/python.exe -m tests.importers.benchmark --help
node --test tests/ci/changes.test.mjs
```

Focused regressions: **1,023 passed in 84.78 s**. Benchmark entry point passed;
CI routing: **45 passed**. Strict Pyright: zero errors/warnings. GUI fixtures,
subprocess imports, fixture/script paths and representative previews are verified;
this is not a full suite or a hosted CI result.

## Pre-commit validation

Native Windows, base `499629e` plus the final test/documentation scope:

```powershell
uv lock --check
uv run --locked ruff check .
uv run --locked ruff format --check src tests
uv run --locked mypy src
npm run test:types
npm run test:dependencies
uv run --locked pytest --junitxml=.tmp/test-delivery-full.xml
```

All passed: **1,496 application tests in 172.82 s**, mypy (64 source files),
11 type-contract tests and 20 dependency tests. Existing unchanged-scope evidence
covers strict Pyright, 45 CI routing tests and Markdown/spelling/52 link checks.
This is native local evidence; hosted CI has not been run for this revision.
