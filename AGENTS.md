# Agent instructions

Apply to GPT and Codex agents. MUST = mandatory; NEVER = prohibited.

## Communication and scope

- MUST communicate in German unless requested otherwise. Code, identifiers, docs and commits: English.
- MUST distinguish verified facts, assumptions and recommendations. Unimplemented = planned; unverified = open.
- MUST execute only the authorized milestone/stage. DEV-REQ-002: report evidence, then STOP. No next stage without a new instruction.
- NEVER declare a milestone/stage complete before ALL its acceptance criteria are verified. M1 and M2 are accepted; M3–M8 remain planned.
- MUST read [README](README.md), [roadmap](docs/ROADMAP.md), [architecture](docs/architecture/OVERVIEW.md) and task requirements before edits. Use [docs index](docs/README.md) for references.
- MUST keep changes scoped and consistent. NEVER refactor unrelated code. MUST align code, tests, configuration and docs.

## Repository and Git

- MUST preserve user changes. Staged files = owner-reviewed. NEVER modify, unstage, replace or repurpose them without explicit authorization.
- MUST obtain explicit owner authorization for staging, committing, pushing, PR creation and merging, covering the operation and scope.
- MUST work on an authorized dedicated feature branch. Create new branches from `main`; continue related work on its existing branch. Preserve user changes during switches.
- NEVER commit on `main` or detached HEAD. NEVER push to remote `main`, delete it or bypass this restriction via force, `--all`, `--mirror` or alternative destination refs.
- MUST integrate into `main` exclusively through an authorized PR targeting `main`. NEVER merge, rebase or reset local `main` to integrate changes.
- MUST verify the active branch immediately before EACH commit/push. Before push: verify explicit destination ref; after push: verify remote commit.
- MUST stage exact authorized paths only. Before commit: inspect ONLY the staged diff; commit ONLY approved staged scope.
- MUST follow [commit rules](.github/commit-message-instructions.md) before generating messages. Messages MUST describe approved staged changes only; no staged changes = no proposed message.
- Branch creation, PR preparation and stage approval NEVER authorize other Git operations.
- MUST use `.tmp/` for ALL temporary files. Track only `.tmp/.gitkeep`; ignore all other contents.
- MUST obey `.gitattributes` and `.editorconfig`: LF text, CRLF Windows command scripts; NEVER normalize `.forces`.

## Platform and architecture

- MUST use Windows, Python 3.14.6, uv, PySide6, Pydantic, typed Python, Ruff, Pylance, mypy and pytest. Respect `.python-version` and the allowed 3.14 patches in `pyproject.toml`.
- MUST use locked dependencies. Before adding dependencies: check requirements and explain purpose.
- NEVER put domain/import/analysis/storage/playback/rendering logic or validation in Qt widgets. `AppSettings` validates bootstrap settings only.
- MUST keep render frame generation separate from encoding. Independent alpha-overlay and opaque-video outputs remain planned for M6.
- MUST support offline application processing and installed quality checks. NEVER require cloud services. Dependency installation and optional Context7 lookup may use network.

## Recordings and scientific contracts

- MUST treat EVERY original `.forces` file as read-only. NEVER rewrite, format, normalize, redact or remove its data.
- MUST preserve original bytes and unknown JSON fields. NEVER assume a stable schema.
- Authorized complete fixtures: Manta, Kraken, Taron, VoltronNevera and Iron Gwazi in `tests/fixtures/real/`, including ALL GPS and metadata. MUST retain byte-length/SHA-256 tests; see [catalog](docs/development/RECORDINGS.md).
- Iron Gwazi publication was authorized for Stage 0 on 2026-10-13. New recordings require separate authorization; fixture-data permission NEVER replaces Git-operation authorization.
- MUST use [ADR 0002](docs/decisions/0002-forces-source-contract.md). Apple Watch is an owner-confirmed data-availability profile. NEVER fabricate absent GPS/gravity.
- MUST document and cross-check coordinates, axis polarity, time base, filtering and GPS sentinels against original-app evidence and fixtures. NEVER silently infer scientific semantics.

## Validation and evidence

- MUST read instructions/task docs once per working context. Re-read ONLY changed content, unresolved relevant sections or lost context.
- MUST batch independent reads/searches. Parallelize independent checks ONLY without shared mutable files, environments or GUI resources; dependencies MUST remain sequential.
- MUST test changed behavior/public contracts and add bug regression tests. Run focused checks first; repeat ONLY checks affected by edits/failures.
- MUST run required suites once for final content and retain actual runner evidence. NEVER rerun solely because commit/push authorization arrived or a commit was created.
- MUST reuse successful evidence ONLY when relevant contents (including staged files), dependencies, lock files, tools, configuration and environment are demonstrably unchanged. Changed inputs: rerun affected checks. Missing evidence/uncertain equivalence: run required suites.
- MUST record exact commands, results, limitations, platform and tested revision/file scope in the applicable `docs/validation/` report. M1 evidence belongs in [M1 validation](docs/validation/M1.md); M2 evidence MUST be consolidated in [M2 validation](docs/validation/M2.md); NEVER create separate M2 stage reports. Temporary logs: `.tmp/`. NEVER add a cache framework solely for evidence reuse.
- MUST batch Git status/scope checks where practical; retain required commit/push boundary checks. Repeat fixture hashes ONLY for relevant changes, integrity uncertainty or explicit acceptance requirements.
- Before commit, ALL commands below MUST have valid passing evidence for the committed content. Execute from repository root using the [Windows setup](docs/development/SETUP.md); valid evidence MAY be reused under the rule above:

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

- MUST retain strict shared `[tool.pyright]`. Ruff: `py314`, 100 columns, `F`/`COM812`. NEVER weaken checks to obtain a pass.
- MUST require actual runner output; exit code alone is insufficient. NEVER present local/static checks as hosted CI evidence or substitute non-Windows results for Windows/GUI verification.
