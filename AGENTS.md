# Agent instructions

Apply to GPT and Codex agents. MUST = mandatory; NEVER = prohibited.

## Communication and scope

- MUST communicate in German unless requested otherwise. Code, identifiers, docs and commits: English.
- MUST distinguish verified facts, assumptions and recommendations. Unimplemented = planned; unverified = open.
- MUST execute only the authorized scope, report evidence, then STOP. No next stage without a new instruction.
- NEVER declare work complete before ALL applicable acceptance criteria are verified.
- MUST keep this file limited to durable project-wide rules. Milestone status belongs in the roadmap; stage steps, deliverables and specific gates belong in the applicable implementation plan. NEVER update this file solely for implementation progress.
- MUST read [README](README.md), [roadmap](docs/ROADMAP.md), [architecture](docs/architecture/OVERVIEW.md), applicable requirements and implementation plan before edits. Use [docs index](docs/README.md) for references.
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

- MUST use native Windows, uv, PySide6, Pydantic, typed Python, Ruff, Pylance, mypy and pytest. Runtime/tool versions and compatibility constraints come from repository configuration and the [Windows setup](docs/development/SETUP.md); NEVER duplicate version pins here.
- MUST use locked dependencies. Before adding dependencies: check requirements and explain purpose.
- NEVER put domain/import/analysis/storage/playback/rendering logic or validation in Qt widgets. MUST follow documented subsystem boundaries.
- MUST keep render frame generation separate from encoding and preserve independent transparent-overlay and opaque-video outputs.
- MUST support offline application processing and installed quality checks. NEVER require cloud services. Dependency installation and optional Context7 lookup may use network.

## Recordings and scientific contracts

- MUST treat EVERY original `.forces` file as read-only. NEVER rewrite, format, normalize, redact or remove its data.
- MUST preserve original bytes and unknown JSON fields. NEVER assume a stable schema.
- MUST preserve ALL data in authorized fixtures, including GPS and metadata, and retain byte-length/SHA-256 tests. Fixture inventory and authorization history belong in the [catalog](docs/development/RECORDINGS.md).
- New recordings require separate authorization; fixture-data permission NEVER replaces Git-operation authorization.
- MUST follow applicable documented source contracts and ADRs. NEVER fabricate absent sensor/GPS data.
- MUST document and cross-check coordinates, axis polarity, time base, filtering and GPS sentinels against original-app evidence and fixtures. NEVER silently infer scientific semantics.

## Validation and evidence

- MUST complete milestone acceptance entirely on native Windows locally: verify ALL criteria, finalize the validation report and completion status, then run checks affected by final documentation BEFORE staging/commit/push.
- MUST treat PR CI as secondary validation and a merge gate, NEVER as a prerequisite for local milestone acceptance. Local completion NEVER authorizes Git operations or another stage.
- MUST include final acceptance documentation in the initial delivery. NEVER add a completion-only commit solely because CI became green; record hosted outcomes in PR metadata. CI failures MUST block merge and be investigated; acceptance evidence invalidated by a defect MUST be corrected.
- MUST read instructions/task docs once per working context. Re-read ONLY changed content, unresolved relevant sections or lost context.
- MUST batch independent reads/searches. Parallelize independent checks ONLY without shared mutable files, environments or GUI resources; dependencies MUST remain sequential.
- MUST test changed behavior/public contracts and add bug regression tests. Run focused checks first; repeat ONLY checks affected by edits/failures.
- MUST run required suites once for final content and retain actual runner evidence. NEVER rerun solely because commit/push authorization arrived or a commit was created.
- MUST reuse successful evidence ONLY when relevant contents (including staged files), dependencies, lock files, tools, configuration and environment are demonstrably unchanged. Changed inputs: rerun affected checks. Missing evidence/uncertain equivalence: run required suites.
- MUST record exact commands, results, limitations, platform and tested revision/file scope in `docs/validation/` as required by the applicable plan. Stage-specific report structure belongs in that plan. Temporary logs: `.tmp/`. NEVER add a cache framework solely for evidence reuse.
- MUST batch Git status/scope checks where practical; retain required commit/push boundary checks. Repeat fixture hashes ONLY for relevant changes, integrity uncertainty or explicit acceptance requirements.
- Before commit, ALL required checks in the [Windows setup](docs/development/SETUP.md) MUST have valid passing evidence for the committed content. Execute from repository root; evidence MAY be reused only under the rule above.
- MUST retain configured lint, format and strict type-checking rules. NEVER weaken checks to obtain a pass.
- MUST require actual runner output; exit code alone is insufficient. NEVER present local/static checks as hosted CI evidence or substitute non-Windows results for Windows/GUI verification.
