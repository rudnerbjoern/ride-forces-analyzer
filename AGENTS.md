# Agent instructions

Apply to GPT and Codex agents. MUST = mandatory; NEVER = prohibited.

## Highest-priority project rules: simplicity and authorized scope

- MUST give these simplicity and scope rules the highest priority within project instructions.
- MUST keep simple tasks simple and choose the simplest solution that fully satisfies the owner's request, reusing existing code and workflows.
- NEVER make a simple task unnecessarily complex or turn it into a broader engineering project. NEVER introduce unnecessary complexity, abstractions, tools, frameworks or processes.
- NEVER expand task scope under any circumstances without the owner's prior explicit permission. Useful, recommended or related work is NEVER automatically authorized.
- NEVER invent requirements or act on assumptions or ideas about tasks the owner has not assigned. MUST perform only the requested work and necessary checks, then STOP.

## Communication and scope

- MUST communicate in German unless requested otherwise. Code, identifiers, docs and commits: English.
- MUST distinguish verified facts, assumptions and recommendations. Unimplemented = planned; unverified = open.
- MUST execute only the authorized scope, report evidence, then STOP. No next stage without a new instruction.
- NEVER declare work complete before ALL applicable acceptance criteria are verified.
- MUST keep this file limited to durable project-wide rules. Milestone status belongs in the roadmap; stage steps, deliverables and specific gates belong in the applicable implementation plan. NEVER update this file solely for implementation progress.
- MUST read [README](README.md), [roadmap](docs/ROADMAP.md), [architecture](docs/architecture/README.md), applicable requirements and implementation plan before edits. Use [docs index](docs/README.md) for references.
- MUST keep changes scoped and consistent. NEVER refactor unrelated code. MUST align code, tests, configuration and docs.

## Documentation: current state, never development history

- MUST describe the current behavior, contracts, relevant decisions, planned work and known limits. MUST update existing descriptions in place and consolidate superseded content. NEVER append sections for individual chat turns, UI adjustments, bug fixes or test reruns.
- NEVER maintain development diaries, chronological implementation narratives, intermediate failure/fix reports or accumulating lists of historical test counts, revisions and commands in project documentation. An executed test or completed change alone NEVER justifies a documentation addition.
- NEVER create or extend a validation report for routine changes unless the owner or applicable implementation/acceptance plan explicitly requires one. Ordinary changes need only relevant behavior/contract documentation and a concise validation result in the response; actual runner logs belong in `.tmp/`.
- Required validation reports MUST summarize the final tested scope in one compact account: commands, results, platform, revision/file scope and remaining limits. MUST replace obsolete evidence rather than append another run history. NEVER copy terminal output, session progress, repeated command lists or intermediate troubleshooting into tracked documentation.
- MUST preserve necessary scientific evidence, ADR rationale and recording authorization in their designated documents. This exception NEVER authorizes unrelated implementation or test history.

## Repository and Git

- MUST use [github-delivery](.agents/skills/github-delivery/SKILL.md) for Git/GitHub delivery; reuse its helpers and authoritative commit policy. NEVER generate replacement operation scripts. Skill use NEVER grants mutation authorization.
- MUST preserve user changes. Staging is a review marker and MUST NEVER block authorized working-tree changes or trigger a confirmation request. Working copies of staged files MAY be edited without separate authorization; NEVER modify, unstage, replace or repurpose index entries without explicit owner authorization.
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

- MUST keep development and local regression checks on native Windows with uv, PySide6, Pydantic, typed Python, Ruff, Pylance, mypy and pytest. Linux/macOS are native distribution-build and runtime-validation targets, not additional developer setups. Runtime/tool versions and compatibility constraints come from repository configuration and the [Windows setup](docs/development/SETUP.md); NEVER duplicate version pins here.
- MUST use locked dependencies. Before adding dependencies: check requirements and explain purpose.
- MUST maintain architecture exclusively in the twelve arc42 chapters under `docs/architecture/`; navigate via their README index and read task-relevant chapters. MUST use Mermaid for suitable diagrams. NEVER introduce a parallel architecture overview; link existing ADRs from chapter 09.
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

- MUST complete local Windows development acceptance before staging/commit/push: verify applicable criteria, finalize any explicitly required report/status and run checks affected by final documentation. Linux/macOS distribution acceptance additionally requires native target package builds and execution checks; NEVER infer it from Windows/static results.
- MUST treat PR CI as secondary validation and a merge gate, NEVER as a prerequisite for local milestone acceptance. Local completion NEVER authorizes Git operations or another stage.
- MUST include explicitly required final acceptance documentation in the initial delivery; this NEVER requires a report for routine changes without an applicable requirement. NEVER add a completion-only commit solely because CI became green; record hosted outcomes in PR metadata. CI failures MUST block merge and be investigated; acceptance evidence invalidated by a defect MUST be corrected in place.
- MUST read instructions/task docs once per working context. Re-read ONLY changed content, unresolved relevant sections or lost context.
- MUST batch independent reads/searches. Parallelize independent checks ONLY without shared mutable files, environments or GUI resources; dependencies MUST remain sequential.
- MUST test changed behavior/public contracts and add bug regression tests. Run focused checks first; repeat ONLY checks affected by edits/failures.
- MUST keep skill/tool regression suites separate from application test discovery. Run them ONLY when their implementation, tests or relevant dependencies change; ordinary application changes and delivery operations NEVER require them.
- MUST run required suites once for final content and retain actual runner evidence. NEVER rerun solely because commit/push authorization arrived or a commit was created.
- MUST reuse successful evidence ONLY when relevant contents (including staged files), dependencies, lock files, tools, configuration and environment are demonstrably unchanged. Changed inputs: rerun affected checks. Missing evidence/uncertain equivalence: run required suites.
- MUST record exact commands, results, limitations, platform and tested revision/file scope in `docs/validation/` as required by the applicable plan. Stage-specific report structure belongs in that plan. Temporary logs: `.tmp/`. NEVER add a cache framework solely for evidence reuse.
- MUST batch Git status/scope checks where practical; retain required commit/push boundary checks. Repeat fixture hashes ONLY for relevant changes, integrity uncertainty or explicit acceptance requirements.
- Before commit, ALL required checks in the [Windows setup](docs/development/SETUP.md) MUST have valid passing evidence for the committed content. Execute from repository root; evidence MAY be reused only under the rule above.
- MUST retain configured lint, format and strict type-checking rules. NEVER weaken checks to obtain a pass.
- MUST require actual runner output; exit code alone is insufficient. NEVER present local/static checks as hosted CI evidence or substitute non-Windows results for Windows/GUI verification.
