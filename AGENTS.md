# Instructions for Codex

## Communication and scope

- Communicate with the user in German unless another language is requested. Write source
  code, identifiers, technical documentation and commit messages in English.
- Distinguish verified facts, assumptions and recommendations. Mark unimplemented features
  as planned and unverifiable acceptance criteria as open.
- Implement one milestone at a time. Do not mark a milestone complete until every acceptance
  criterion is verified. This delivery covers M1; do not implement M2 without a new
  owner instruction.
- Read [README.md](README.md), the [roadmap](docs/ROADMAP.md) and
  [architecture](docs/architecture/OVERVIEW.md) before changing the project. Use the
  [documentation index](docs/README.md) to find development guides and validation evidence.

## Repository and Git

- Preserve all existing user changes, including unrelated staged and unstaged changes.
- Treat staged files as reviewed by the user. Never modify, unstage, replace or include them
  in another operation unless explicitly requested.
- Stage files only within the scope explicitly authorized for committing. Before a commit,
  inspect only the staged diff and commit only the exact staged scope approved by the user.
- Never commit on local `main` and never push to remote `main`, including force pushes,
  deletion or pushing another source branch to `main`. Never bypass this rule with
  `--all`, `--mirror` or a different push destination.
- Always create a dedicated branch from `main` for each change before committing.
  Continue related work on that branch; preserve existing working-tree and staged changes
  when creating or switching branches. Do not commit with a detached HEAD.
- Before every authorized commit or push, verify the active branch and, for a push,
  the explicit destination ref. Both must be the intended working branch, never `main`.
- Transfer changes to `main` exclusively through a pull request targeting `main`.
  Do not integrate changes into local `main` with a direct merge, rebase or reset.
  Creating a branch or preparing a pull request does not authorize staging, committing,
  pushing or merging; respect the owner's current authorization for each action.
- Before generating or proposing a commit message, read and follow
  [.github/commit-message-instructions.md](.github/commit-message-instructions.md).
  Base messages exclusively on the approved staged changes; the message rules do not
  authorize staging or committing.
- Keep edits narrowly scoped, reviewable and consistent with existing conventions. Avoid
  opportunistic refactoring. Keep code, tests, configuration and documentation aligned.
- Use the repository-root `.tmp/` directory for all temporary files. Only `.gitkeep` may be
  tracked there; other contents must remain ignored.
- Respect `.gitattributes` and `.editorconfig`: LF text, CRLF Windows command scripts and
  no byte normalization or formatting of `.forces` recordings.

## Platform and architecture

- Target Windows, Python 3.14.6, uv, PySide6, Pydantic, typed Python, Ruff, Pylance,
  mypy and pytest. `.python-version` pins Python; `pyproject.toml` allows later 3.14 patches.
- Use locked dependencies for reproducible validation. Explain the purpose of new
  dependencies and check project requirements before adding them.
- Keep domain/import/analysis/storage/playback/rendering logic out of UI widgets.
- Keep validation outside widgets. The M1 `AppSettings` model covers bootstrap settings,
  not recording schemas.
- Separate render frame generation from encoding; independent alpha-overlay and
  opaque-video outputs are planned for M6.
- All application processing must work offline. Avoid mandatory cloud services.
  Development dependency installation and optional Context7 documentation lookup may
  require network access; installed local quality checks must work offline.

## Recordings and scientific contracts

- Use `.forces` recordings as **read-only** input; never rewrite them in place.
- Preserve unknown JSON fields and original file bytes. Do not assume a stable source schema.
- The owner expressly authorizes using and publishing the complete Manta, Kraken,
  Taron and VoltronNevera recordings in `tests/fixtures/real/` for project tests and
  development, including all embedded GPS positions and metadata. The
  [recording catalog](docs/development/RECORDINGS.md) lists their exact filenames,
  original sizes and SHA-256 digests. Keep all four read-only and covered by integrity tests.
- This authorization applies to those four recordings. Do not automatically add or
  publish additional recordings without their own authorization.
- Domain coordinates, axis polarity, time base, filtering and GPS sentinel semantics
  require explicit documentation, fixtures and cross-checks against the original Ride
  Forces app. Never silently assume their meaning.

## Validation and evidence

- Add or update tests for changed behavior and public contracts; provide regression tests
  for bug fixes. Run the smallest relevant validation first, then required project suites.
- Follow the [Windows development guide](docs/development/SETUP.md). Before an authorized
  commit, all of these checks must pass from the repository root:

  ```powershell
  uv lock --check
  uv run ruff check .
  uv run ruff format --check src tests
  uv run mypy src
  npm run typecheck
  npm run test:types
  npm run test:dependencies
  uv run pytest
  npm run test:docs
  ```

- Pylance and Pyright share strict `[tool.pyright]` configuration. Ruff targets `py314`,
  uses a 100-character line limit and the owner's `F`/`COM812` rule selection.
- Do not claim Windows GUI operation or Windows CI success without actually testing
  those environments. A successful exit code without runner output is insufficient.
- Record results and material limitations in [M1 validation](docs/validation/M1.md).
  Local checks and static workflow validation do not prove GitHub-hosted CI success.
