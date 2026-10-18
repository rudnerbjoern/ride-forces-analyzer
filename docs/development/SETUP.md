# Windows development setup

Use native Windows PowerShell and a desktop session. WSL/offscreen tests do not
verify the supported Qt environment. Run checks from the repository root.

## Install and start

```powershell
.\setup.ps1
.\start.ps1
```

[Setup](../../setup.ps1) creates `.venv` using Python from `.python-version` and
`uv sync --locked --all-extras --group dev`. It uses uv 0.13.0 from
`.tmp/uv-windows/uv.exe` or PATH; if neither exists, it downloads the official
Windows x64 release into `.tmp/`. A mismatched uv version fails with a clear error.
It does not update locks, change PATH or activate an environment. Repeating setup
synchronizes the existing environment. Initial installation requires network access.

[Start](../../start.ps1) runs `.venv/Scripts/python.exe -m ride_forces_analyzer`
from the repository root and returns its exit code after the window closes.
It performs no dependency installation. Both scripts also work when called from
another directory and restore the caller's working directory.

For all development checks, install Node.js 26.11.1 from
[Node downloads](https://nodejs.org/en/download), matching `.node-version`, with
its bundled npm. Then run:

```powershell
.\setup.ps1 -Development
```

This additionally verifies the Node version and runs locked `npm ci` with its
cache under `.tmp/`. Node is a development dependency only. Optional Python
packages do not imply that their planned product features are implemented.

If Windows blocks local scripts, invoke the requested script for that process:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

The scripts target Windows x64; other architectures are unverified. Source
recordings are never installation inputs and remain read-only.

## Video export tools

Run `.\setup.ps1 -VideoExport` to install the FFmpeg full build pinned by
[ffmpeg.json](../../ffmpeg.json), including its SHA-256 checksum. Native curl/tar
fetch and extract the publisher archive under `.tmp/`; repeat setup reuses the
installed encoder. Cleaning `.tmp/` removes this optional tool installation.
The export dialog can also use an existing ffmpeg.exe without downloading anything.
Installed export processing is offline. Pillow is already a locked render extra;
no new Python dependency is introduced. The full build supports Vulkan ProRes
and NVIDIA NVENC when the actual GPU probe succeeds; CPU encoding remains usable.
See [export usage](../../README.md) and [contracts](../implementation/VIDEO_EXPORT.md).

## Manual equivalent

With uv 0.13.0 on PATH (or use `.tmp\uv-windows\uv.exe`):

```powershell
uv python install 3.14.6
uv sync --locked --all-extras --group dev
npm ci --no-audit --no-fund --cache .tmp/npm-cache
uv run --locked python -m ride_forces_analyzer
```

The Python and Node versions come from `.python-version` and `.node-version`;
`pyproject.toml`, `uv.lock` and `package-lock.json` own dependency constraints.
The Windows `py` launcher is unnecessary. Temporary downloads/logs belong in
`.tmp/`; only its `.gitkeep` is tracked.

## Required project checks

After closing the application, with the configured Node and uv on PATH:

```powershell
uv lock --check
uv run --locked ruff check .
uv run --locked ruff format --check src tests
uv run --locked mypy src
npm run typecheck
npm run test:types
npm run test:dependencies
node --test tests/ci/changes.test.mjs
uv run --locked pytest
npm run test:docs
```

For separate package verification, `uv build` writes ignored `dist/` artifacts.
Installed checks work offline. Coverage and limits are described in
[code quality](CODE_QUALITY.md), [documentation tests](DOCUMENTATION_TESTS.md) and
[CI selection](CI.md). Application pytest/Test Explorer discovers `tests/` only;
the [delivery skill](../../.agents/skills/github-delivery/SKILL.md) owns its separate
regression commands, run only for affected skill inputs.

Follow [AGENTS.md](../../AGENTS.md) for evidence reuse, local acceptance before
publication and explicit Git authorization. PR CI is secondary validation and a
merge gate; local success grants no delivery or next-stage permission. Record
exact commands, runner results, platform, tested scope and limitations in the
applicable `docs/validation/` report; temporary logs stay in `.tmp/`.

## VS Code and Test Explorer

Open the folder in Windows VS Code and install the extensions recommended in
`.vscode/extensions.json`: Python, Pylance, Ruff, markdownlint and Code Spell Checker.
The default interpreter is `.venv/Scripts/python.exe`. An existing interpreter
selection takes precedence: use **Python: Select Interpreter** to select that file.

The Python Environments extension uses `uv pip` for package inspection when uv
is available on VS Code's process PATH; pip is not installed in `.venv`.
Workspace settings enable this behavior and register the root project as a venv.
The package-manager identifier remains `ms-python.python:pip`; the extension
substitutes uv when available. The setup script's `.tmp/uv-windows/uv.exe` is
project-local and is not automatically on VS Code's PATH. For the IDE package
view, make uv available on your user PATH and fully restart VS Code afterward.
Reloading a window alone may retain the old process PATH. Keep dependency changes
in `pyproject.toml` and the lockfile rather than installing packages through the UI.

The **Testing** view discovers pytest under `tests/`, refreshes on Python saves
and supports individual tests or **Run All Tests**. unittest is disabled; the
working directory is the repository root. npm and skill tests run separately.
Pylance/Pyright share strict `[tool.pyright]` settings in `pyproject.toml`; Ruff
uses the locked `.venv/Scripts/ruff.exe` and formats on save.

Only shared `.vscode/settings.json` and `extensions.json` are eligible for Git.
`.editorconfig` and `.gitattributes` define UTF-8/LF text, indentation and CRLF
Windows command scripts; `.forces` files are excluded from normalization.
