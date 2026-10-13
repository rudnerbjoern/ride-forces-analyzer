# Python validation and code quality

The project uses Pydantic for runtime validation, Ruff for Python linting and
formatting, and Pylance for editor type checking. mypy and Pyright provide
repeatable command-line checks. All checks work offline after dependencies have
been installed.

## Runtime validation

`src/ride_forces_analyzer/config.py` defines `AppSettings`, an immutable Pydantic
model used by the Qt startup function. The model validates a nonempty window
title and integer dimensions from 1 through 16,777,215 pixels, Qt's documented
maximum widget dimension. The upper bound prevents Qt conversion overflows and
unsupported sizes before startup. Strict validation rejects coercion from
strings, floats and booleans. Defaults are also validated, and unknown
application-setting keys are rejected.

This model applies only to bootstrap window settings. It is not a recording
schema. M2 Stage 1 now supplies immutable canonical/source representations;
[Stage 5](IMPORT_SERVICE.md) adds complete importing; calibration remains planned.
Original recording bytes remain
read-only.

The `frozen=True` class argument lets type checkers recognize immutability.
The mypy Pydantic plugin generates typed constructor signatures and rejects
extra arguments. Pylance/Pyright use Pydantic's native typing information.

## Editor setup

The workspace recommends Microsoft Python, Pylance and Ruff. Its Windows
interpreter is `.venv/Scripts/python.exe`. Pylance is explicitly selected as the
language server and checks the workspace rather than only open files.

`[tool.pyright]` in `pyproject.toml` is the shared source of truth for strict
Pylance and Pyright analysis. It covers `src/` and `tests/`, targets Python 3.14
on Windows, and excludes temporary files and dependencies. Pylance uses the
selected interpreter; the CLI resolves the project's `.venv`.

Ruff linting is enabled and its VS Code extension uses `.venv/Scripts/ruff.exe`,
matching the locked development tool. Ruff formats Python on save and applies
its fixes and import sorting on explicit saves. These workspace settings take
precedence over user-level Python formatter choices without modifying those
user settings.

## Command-line checks

Follow the execution and evidence rules in [AGENTS.md](../../AGENTS.md#validation-and-evidence):
use focused checks while editing, then run all required suites once for the final content.
Reuse successful results for a later authorized commit or push only while the checked
inputs and environment remain unchanged and actual runner evidence is available.

Complete the [Windows development setup](SETUP.md), then run:

```powershell
uv run ruff check .
uv run ruff format --check src tests
uv run mypy src
npm run typecheck
npm run test:types
npm run test:dependencies
uv run pytest
```

Ruff targets Python 3.14 with a 100-character line limit and enables only `F`
and `COM812` lint rules. Its formatter writes LF line endings and retains magic
trailing-comma behavior. The formatter check reports drift without rewriting files.
Ruff warns that `COM812` can conflict with formatting; the rule is enabled by
explicit project preference.
mypy uses strict mode and the Pydantic plugin. Pyright is pinned in
`package-lock.json`; it is a development tool, not an application dependency.

Pylance and Pyright share configuration but are separate tools with potentially
different bundled engine versions. CLI success is not a claim that VS Code's
Problems view was manually inspected.

## Tests

- `tests/test_project.py` verifies the project version, exact five-recording inventory
  and each original file's byte length and SHA-256 independently. The authorized
  [recording catalog](RECORDINGS.md) covers Manta, Kraken, Taron, Voltron Nevera and Iron Gwazi.
- `tests/test_settings.py` exercises defaults, custom settings, JSON round trips,
  invalid dimensions and types, both valid dimension boundaries, invalid titles,
  unknown keys and immutability.
- `tests/test_gui.py` starts the native Windows Qt application with default and
  custom Pydantic settings and checks the resulting title and dimensions.
- `tests/test_ruff.py` verifies unused-import and missing-trailing-comma diagnostics and
  verifies that the formatter accepts LF-formatted code and rejects drift and CRLF.
- `tests/types/pydantic.test.mjs` checks typed constructors and frozen fields
  through Pyright using the shared project settings. Temporary contracts are
  stored under `.tmp/` and explicitly included in their test configuration.
  The tests require a positive analyzed-file count and inspect diagnostic rules,
  rather than relying solely on process exit status.
- `tests/test_source_models.py`, `tests/test_recording_models.py` and
  `tests/test_import_results.py` verify [canonical model](CANONICAL_MODELS.md)
  ownership, immutability, source type retention, absence, diagnostics and results.
- `tests/types/recording.test.mjs` adds public model constructor, immutable mapping,
  frozen-field and literal outcome-tag contracts to `npm run test:types`.
- `tests/test_motion_parser.py` covers all five complete motion sequences and
  synthetic FR-011–016 defects; the type-contract suite also verifies narrowing
  of the motion-specific subset result. See [motion parsing](MOTION_PARSING.md).
- `tests/test_decoder.py` verifies Stage 2 grammar/encoding/dispatch failures,
  input/resource budgets, exact source retention and bounded read-only I/O.
  The Pyright suite also narrows the decoder-specific result; see
  [strict decoding](STRICT_DECODING.md).
- `tests/test_optional_parser.py` verifies Stage 4 metadata defaults, arbitrary
  ordered attributes and every real GPS fix, plus optional defects and local
  diagnostic budgets. Pyright also narrows the optional-specific subset result;
  see [optional parsing](OPTIONAL_PARSING.md).
- `tests/test_import_service.py` verifies full Path/bytes imports, all original
  data, determinism/concurrency, aggregate diagnostic limits, safe recovery and
  fresh-process Qt/network/write guards. `tests/benchmark_importer.py` records
  Windows timings and traced Python allocation peaks without performance assertions;
  see [the public service](IMPORT_SERVICE.md).
- `tests/dependencies/security.test.mjs` checks the actual Node dependency consumers:
  two TOML configuration parsers, inherited KaTeX trust rejection and three
  micromark math-rendering contracts. See the [security follow-up](../validation/DEPENDABOT.md)
  for override rationale and the remaining advisory. These are development-tool tests,
  not application rendering features.

The PR-only Windows quality job runs Ruff, formatter checks, mypy, Pyright, the
type contracts, dependency regressions and pytest when code/test inputs change.
Documentation linting remains a separate job selected by Markdown changes;
see [CI selection](CI.md) for routing, failure handling and the required merge gate.

## References

Configuration was checked through Context7 against the official documentation:

- [Pydantic model configuration](https://docs.pydantic.dev/latest/concepts/config/)
- [Pydantic mypy integration](https://docs.pydantic.dev/latest/integrations/mypy/)
- [Ruff editor settings](https://docs.astral.sh/ruff/editors/settings/)
- [Pylance and Pyright configuration](https://github.com/microsoft/pylance-release/blob/main/USING_WITH_PYRIGHT.md)

The widget-size contract was cross-checked through Context7 against the
[Qt QWidget size documentation](https://doc.qt.io/qt-6/qwidget.html#QWIDGETSIZE_MAX).
