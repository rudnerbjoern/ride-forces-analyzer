# Sequential Codex prompts — DEV-REQ-002

**Use one prompt per invocation.** These prompts are instructions for future
implementation, not authorization to perform that implementation now.

Each prompt must be used after reviewing the previous stage's code, tests
and documentation. The prompts deliberately stop short of automatic
staging/committing/pushing; obtain explicit authorization as required by AGENTS.md.

## Shared instructions (apply to every prompt)

> Read AGENTS.md, docs/ROADMAP.md, docs/architecture/OVERVIEW.md,
> docs/requirements/DEV-REQ-002-forces-importer.md,
> docs/requirements/FORMAT-ANALYSIS.md, and
> docs/implementation/DEV-REQ-002/PLAN.md first.
> Follow the current Windows Python 3.14.6/uv toolchain.
> Respect the five current read-only recordings and all their GPS data.
> Use English in all code, documentation and commit messages.
> Work only on an authorized feature branch, never directly on main.
> Do not stage, commit, push or merge without explicit owner authorization.
> Run focused tests, then applicable project quality checks.
> Report actual evidence and unverified items; stop after this stage.

## Prompt 0 — schema inventory and ADR

Copy the following prompt into Codex:

```text
Read AGENTS.md, docs/ROADMAP.md, docs/architecture/OVERVIEW.md,
docs/requirements/DEV-REQ-002-forces-importer.md,
docs/requirements/FORMAT-ANALYSIS.md, and
docs/implementation/DEV-REQ-002/PLAN.md first.
Follow the current Windows Python 3.14.6/uv toolchain.
Respect the five current read-only recordings and all their GPS data.
Use English in all code, documentation and commit messages.
Work only on an authorized feature branch, never directly on main.
Do not stage, commit, push or merge without explicit owner authorization.
Run focused tests, then applicable project quality checks.
Report actual evidence and unverified items; stop after this stage.

Task: Inspect all five .forces fixtures recursively, including every JSON field/type, optionality, nesting and sequence length. Reconcile findings with FORMAT-ANALYSIS.md. Produce a reproducible inventory test/snapshot and document decisions on API contracts, source byte retention, resource limits and optional GPS error handling in a new ADR. Do not implement the importer yet. Link decisions to FR-001, FR-004, FR-007, FR-024 and FR-030. Confirm fixture integrity.

Produce at the end:
- Files changed and requirement IDs covered.
- Exact test commands and actual results.
- Known assumptions, risks and next stage readiness.
- Confirmation that no original .forces file was altered.
Do not start another stage.
```

## Prompt 1 — canonical typed models

Copy the following prompt into Codex:

```text
Read AGENTS.md, docs/ROADMAP.md, docs/architecture/OVERVIEW.md,
docs/requirements/DEV-REQ-002-forces-importer.md,
docs/requirements/FORMAT-ANALYSIS.md, and
docs/implementation/DEV-REQ-002/PLAN.md first.
Follow the current Windows Python 3.14.6/uv toolchain.
Respect the five current read-only recordings and all their GPS data.
Use English in all code, documentation and commit messages.
Work only on an authorized feature branch, never directly on main.
Do not stage, commit, push or merge without explicit owner authorization.
Run focused tests, then applicable project quality checks.
Report actual evidence and unverified items; stop after this stage.

Task: Implement only the immutable canonical models and structured diagnostics, using existing domain/importers package boundaries. Include source provenance, lossless source envelope ownership, optional metadata and typed data concepts. Add synthetic model tests covering mutation resistance, absent-vs-zero, diagnostic ordering and source value type retention. No file decoder, iOS math, Qt integration or extra features. Satisfy Stage 1 acceptance and FR-002–006, FR-023, FR-027.

Produce at the end:
- Files changed and requirement IDs covered.
- Exact test commands and actual results.
- Known assumptions, risks and next stage readiness.
- Confirmation that no original .forces file was altered.
Do not start another stage.
```

## Prompt 2 — strict parser foundation

Copy the following prompt into Codex:

```text
Read AGENTS.md, docs/ROADMAP.md, docs/architecture/OVERVIEW.md,
docs/requirements/DEV-REQ-002-forces-importer.md,
docs/requirements/FORMAT-ANALYSIS.md, and
docs/implementation/DEV-REQ-002/PLAN.md first.
Follow the current Windows Python 3.14.6/uv toolchain.
Respect the five current read-only recordings and all their GPS data.
Use English in all code, documentation and commit messages.
Work only on an authorized feature branch, never directly on main.
Do not stage, commit, push or merge without explicit owner authorization.
Run focused tests, then applicable project quality checks.
Report actual evidence and unverified items; stop after this stage.

Task: Implement Path and bytes-based strict JSON decode with UTF-8 validation, duplicate-key rejection, size/sequence limits, object-root requirement, schema version dispatch restricted to 2.2.0, raw byte preservation and deterministic structured errors. Write negative tests for all decoder failure conditions. No motion conversion beyond necessary schema scaffolding. Meet FR-001, FR-003–010, FR-024, FR-026.

Produce at the end:
- Files changed and requirement IDs covered.
- Exact test commands and actual results.
- Known assumptions, risks and next stage readiness.
- Confirmation that no original .forces file was altered.
Do not start another stage.
```

## Prompt 3 — vector sequence and index validation

Copy the following prompt into Codex:

```text
Read AGENTS.md, docs/ROADMAP.md, docs/architecture/OVERVIEW.md,
docs/requirements/DEV-REQ-002-forces-importer.md,
docs/requirements/FORMAT-ANALYSIS.md, and
docs/implementation/DEV-REQ-002/PLAN.md first.
Follow the current Windows Python 3.14.6/uv toolchain.
Respect the five current read-only recordings and all their GPS data.
Use English in all code, documentation and commit messages.
Work only on an authorized feature branch, never directly on main.
Do not stage, commit, push or merge without explicit owner authorization.
Run focused tests, then applicable project quality checks.
Report actual evidence and unverified items; stop after this stage.

Task: Implement motion acceleration/gravity parsing, finite numeric-string conversion, valid sample-rate handling, sequence-length and component validation, structural vector preservation and independently bounded indices. Preserve original strings. Explicitly include Taron gravityIndex before startIndex. Do not calculate rider G forces or assert GPS/time semantics. Build parametric tests across all five recordings and synthetic malformed cases. Include owner-default rate 50 only for absence, with explicit provenance, and the Apple Watch absence policy in ADR 0002; never fabricate gravity. Meet FR-011–016.

Produce at the end:
- Files changed and requirement IDs covered.
- Exact test commands and actual results.
- Known assumptions, risks and next stage readiness.
- Confirmation that no original .forces file was altered.
Do not start another stage.
```

## Prompt 4 — metadata, attributes and GPS

Copy the following prompt into Codex:

```text
Read AGENTS.md, docs/ROADMAP.md, docs/architecture/OVERVIEW.md,
docs/requirements/DEV-REQ-002-forces-importer.md,
docs/requirements/FORMAT-ANALYSIS.md, and
docs/implementation/DEV-REQ-002/PLAN.md first.
Follow the current Windows Python 3.14.6/uv toolchain.
Respect the five current read-only recordings and all their GPS data.
Use English in all code, documentation and commit messages.
Work only on an authorized feature branch, never directly on main.
Do not stage, commit, push or merge without explicit owner authorization.
Run focused tests, then applicable project quality checks.
Report actual evidence and unverified items; stop after this stage.

Task: Implement optional metadata, ordered arbitrary attributes and independent GPS fix parsing. Use owner-default ridingPosition Seated only for absence, with explicit provenance and unchanged source data. Preserve any negative GPS speed, course and accuracy raw value; surface warnings without assuming units or sentinel meaning. Test missing Manta location/weather, missing Taron/Voltron ridingPosition, Taron Row and Seat, differing GPS lengths, absent Iron Gwazi GPS/gravity, and defective optional GPS fixes. Meet FR-009–010, FR-017–022 and FR-025.

Produce at the end:
- Files changed and requirement IDs covered.
- Exact test commands and actual results.
- Known assumptions, risks and next stage readiness.
- Confirmation that no original .forces file was altered.
Do not start another stage.
```

## Prompt 5 — importer integration and resilience

Copy the following prompt into Codex:

```text
Read AGENTS.md, docs/ROADMAP.md, docs/architecture/OVERVIEW.md,
docs/requirements/DEV-REQ-002-forces-importer.md,
docs/requirements/FORMAT-ANALYSIS.md, and
docs/implementation/DEV-REQ-002/PLAN.md first.
Follow the current Windows Python 3.14.6/uv toolchain.
Respect the five current read-only recordings and all their GPS data.
Use English in all code, documentation and commit messages.
Work only on an authorized feature branch, never directly on main.
Do not stage, commit, push or merge without explicit owner authorization.
Run focused tests, then applicable project quality checks.
Report actual evidence and unverified items; stop after this stage.

Task: Expose the public, Qt-independent import service returning full typed recording, original provenance and ordered diagnostics. Prove byte-for-byte preservation and deterministic repeated parsing for all five owner-supplied fixtures. Test unknown fields, resource limits, error recovery, no network and no writes. Record actual performance measurements on Windows. Do not implement library, GUI, analysis or export. Meet FR-028–030 and relevant ACs.

Produce at the end:
- Files changed and requirement IDs covered.
- Exact test commands and actual results.
- Known assumptions, risks and next stage readiness.
- Confirmation that no original .forces file was altered.
Do not start another stage.
```

## Prompt 6 — validate and prepare review

Copy the following prompt into Codex:

```text
Read AGENTS.md, docs/ROADMAP.md, docs/architecture/OVERVIEW.md,
docs/requirements/DEV-REQ-002-forces-importer.md,
docs/requirements/FORMAT-ANALYSIS.md, and
docs/implementation/DEV-REQ-002/PLAN.md first.
Follow the current Windows Python 3.14.6/uv toolchain.
Respect the five current read-only recordings and all their GPS data.
Use English in all code, documentation and commit messages.
Work only on an authorized feature branch, never directly on main.
Do not stage, commit, push or merge without explicit owner authorization.
Run focused tests, then applicable project quality checks.
Report actual evidence and unverified items; stop after this stage.

Task: Perform the complete native-Windows checks in AGENTS.md and docs/development/SETUP.md. Create docs/validation/M2.md with exact recorded outcomes for AC-01–AC-10, fixtures, known limits, test-to-requirement traceability and performance observations. Complete acceptance entirely locally; finalize the report and verified completion status in docs/ROADMAP.md before the first delivery commit, then recheck documentation. Review changes with the owner before any staging/commit/push. Following explicit authorization, prepare a draft PR to main; do not merge. PR CI is secondary validation: record outcomes in PR metadata and require selected suites and the final check gate to pass before merge, without a completion-only follow-up commit. If local checks fail or evidence is missing, leave affected criteria open. Investigate CI failures and correct invalidated acceptance evidence.

Produce at the end:
- Files changed and requirement IDs covered.
- Exact test commands and actual results.
- Known assumptions, risks and next stage readiness.
- Confirmation that no original .forces file was altered.
Do not start another stage.
```

## Review gate

Before proceeding to each next prompt, confirm the stage's tests and scope
against [PLAN.md](PLAN.md) and the acceptance matrix in
[DEV-REQ-002](../../requirements/DEV-REQ-002-forces-importer.md).
Any design departure must be documented as an ADR and reviewed rather than
silently modifying the requirement.
