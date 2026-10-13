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
schema. Importing `.forces` files, preserving unknown recording fields and
calibrating data remain planned for M2/M3. Original recording bytes remain
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

Complete the [Windows development setup](SETUP.md), then run:

```powershell
uv run ruff check .
uv run ruff format --check src tests
uv run mypy src
npm run typecheck
npm run test:types
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

The PR-only Windows quality job runs Ruff, formatter checks, mypy, Pyright, the
type contracts and pytest. Documentation linting remains a separate job.

## References

Configuration was checked through Context7 against the official documentation:

- [Pydantic model configuration](https://docs.pydantic.dev/latest/concepts/config/)
- [Pydantic mypy integration](https://docs.pydantic.dev/latest/integrations/mypy/)
- [Ruff editor settings](https://docs.astral.sh/ruff/editors/settings/)
- [Pylance and Pyright configuration](https://github.com/microsoft/pylance-release/blob/main/USING_WITH_PYRIGHT.md)

The widget-size contract was cross-checked through Context7 against the
[Qt QWidget size documentation](https://doc.qt.io/qt-6/qwidget.html#QWIDGETSIZE_MAX).
