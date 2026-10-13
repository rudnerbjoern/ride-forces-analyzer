# Windows development setup

Run commands from the repository root in Windows PowerShell. Use Windows tooling
and the Windows virtual environment for platform acceptance; WSL-only or offscreen
results do not verify the supported desktop environment.

## Install dependencies

Install uv 0.13.0 following the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).
Install Node.js 26.11.1 from the [official Node.js downloads](https://nodejs.org/en/download),
matching `.node-version`, and use its bundled npm. Verify the active executables:

```powershell
uv --version
node --version
npm --version
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:NPM_CONFIG_CACHE = "$PWD/.tmp/npm-cache"
uv python install 3.14.6
uv sync --locked --all-extras --group dev
npm ci --no-audit --no-fund
uv run python --version
```

The Python lock includes runtime, development and optional analysis/render dependencies.
Those optional dependencies are installed for compatibility checks; their product
features remain planned. `package-lock.json` pins the Node development tools.
The Windows `py` launcher is not required. Initial installation needs network access;
installed checks and application processing work offline.

Manually created temporary files and downloaded validation tools belong in `.tmp/`.
Its `.gitkeep` preserves the directory in Git; its other contents are ignored.

## Launch the application

```powershell
uv run python -m ride_forces_analyzer
```

This command opens the minimal native Qt window and blocks until it closes.
A Windows desktop session is required. Import and analysis are not implemented.

## Run project checks

After closing the application, run:

```powershell
uv lock --check
uv run ruff check .
uv run ruff format --check src tests
uv run mypy src
npm run typecheck
npm run test:types
uv run pytest
npm run test:docs
```

These commands cover Python linting, formatting, two type checkers, static typing
contracts, runtime and native GUI tests, Markdown formatting, spelling and local
links. Run focused checks first when changing one boundary. To verify package
construction separately, run `uv build`; outputs go to ignored `dist/`.

CI runs only on `pull_request` events. Its `check` job performs locked Python and
Node installation and all Python quality checks; `documentation` installs Node
tools and runs the documentation suite. Both jobs use `windows-latest`.
See [M1 validation](../validation/M1.md) for actual results and open CI acceptance.

## Branch and pull-request workflow

Create a dedicated working branch from `main` for each change before committing;
continue related work on that branch. Preserve existing local changes when
creating or switching branches. Never commit on `main` or with a detached HEAD,
and never push to remote `main`, including force pushes or pushing another source
branch to `main`. Before an authorized commit or push, verify the active branch and
the explicit push destination.

Changes reach `main` exclusively through a pull request targeting `main`, never
through a direct local merge, rebase or reset. Follow [AGENTS.md](../../AGENTS.md)
for authorization and the [commit-message guide](../../.github/commit-message-instructions.md)
for message format. Stage, commit and push only the scope authorized by the owner.
Creating a draft pull request does not authorize its merge.

## VS Code and Test Explorer

Open the repository folder in Windows VS Code and install the recommended extensions
from `.vscode/extensions.json`: Microsoft Python, Pylance, Ruff, markdownlint and
Code Spell Checker. Complete dependency installation first.

Workspace settings enable pytest for `tests/`, disable unittest and use the repository
root as the test working directory. The default interpreter is the executable
`.venv/Scripts/python.exe`. If an interpreter was selected previously, use
**Python: Select Interpreter** and select `.venv\Scripts\python.exe` (Python 3.14.6);
the default setting does not replace an existing selection.

Open the **Testing** view, refresh discovery if needed and run an individual test or
**Run All Tests**. Discovery also refreshes when Python files are saved. Node-based
documentation and type-contract suites run through npm, separately from pytest discovery.

Only shared `settings.json` and `extensions.json` are eligible for version control;
other `.vscode/` files remain ignored. Pylance and Pyright use `[tool.pyright]` in
`pyproject.toml`; Ruff uses the locked `.venv/Scripts/ruff.exe` and formats on save.
See [code quality](CODE_QUALITY.md) and [documentation tests](DOCUMENTATION_TESTS.md)
for their configurations and test scope.

## Text conventions

`.gitattributes` stores text with LF and uses CRLF for Windows `.bat`/`.cmd` working
files. `.editorconfig` uses UTF-8, spaces, four-column Python indentation and
two-column JSON/JSONC, YAML and JavaScript indentation. Markdown hard line breaks
are preserved. `.forces` files are excluded from byte normalization and editor formatting.

Editor conventions were checked through Context7 against the
[official EditorConfig properties](https://github.com/editorconfig/editorconfig/wiki/EditorConfig-Properties).
