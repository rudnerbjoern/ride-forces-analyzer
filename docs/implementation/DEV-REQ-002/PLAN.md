# DEV-REQ-002 — M2 implementation plan

**Status:** Planned / no importer implemented. All content is in English.
**Normative requirements:** [DEV-REQ-002](../../requirements/DEV-REQ-002-forces-importer.md).
**Source observations:** [Format analysis](../../requirements/FORMAT-ANALYSIS.md).
**Execution prompts:** [PROMPTS.md](PROMPTS.md).

This plan is a **sequence**, not permission to implement every stage in one run.
Implement each stage separately and obtain approval before committing/pushing
as required by [AGENTS.md](../../../AGENTS.md). Reuse the existing branch for
related work; each new independent change begins on a separate branch from `main`.

## Stage 0 — Confirm inputs and choose API boundaries

- Read AGENTS.md, the current roadmap, architecture, setup and both M2 documents.
- Inventory existing `src/ride_forces_analyzer/domain` and `importers` code to
  reuse the current package structure rather than creating duplicate modules.
- Record an ADR for schema-version dispatch, byte ownership/source-envelope
  representation, error/warning severity, bounds on untrusted input and policies
  where DEV-REQ-002 offers alternatives.
- Supply field matrix and nested-type inventory as automated evidence; compare
  against the four documented fixtures. Keep explicit observed/inferred markers.
- **Tests:** fixture digests, no writes, predictable schema-inventory snapshots.
- **Exit:** no ambiguous parser decisions; no production importer yet.
- **Trace:** FR-001, 004, 007, 024, 030; AC-02.

## Stage 1 — Canonical model and diagnostics

- Implement immutable typed objects for scalar/vector readings, source metadata,
  GPS readings, optional attributes and sample collections (prefer compact,
  read-only sequences appropriate for 10K+ samples).
- Define structured diagnostic severity, code, source JSON path, optional index
  and deterministic ordering; model source provenance including byte length
  and SHA-256. Choose clear success/failure typing and expose missing optional
  data distinctly from zero.
- Keep raw unnormalized JSON semantics or raw bytes available independently of
  parsed domain accessors. Avoid Python `dict` mutation leakage.
- Do not import Qt or use calibration equations.
- **Tests:** immutability, equality/determinism, diagnostic shape and source
  ownership; mypy/Pyright contract tests as applicable.
- **Exit:** imported models usable by a synthetic in-memory test without I/O.
- **Trace:** FR-002–006, 023, 027; AC-03, 08.

## Stage 2 — Strict JSON decoder and version dispatch

- Add input adapters for Path and bytes, strict UTF-8 and JSON parsing,
  duplicate-key rejection, root-object validation, bounded file size,
  configurable maximum sequence length and appropriate safety checks.
- Interpret only the supported `2.2.0` schema. Reject unknown versions with
  explicit diagnostics; allow unknown extension fields in a supported schema.
- Preserve original bytes and original JSON value types. Avoid silent
  normalization, timestamps interpretation or URL/network access.
- **Tests:** invalid paths/permissions, empty and malformed inputs, non-UTF-8,
  duplicate keys (including nested), unsupported version, injected field,
  oversized input, full source round trip.
- **Exit:** malformed inputs never appear as successful imports.
- **Trace:** FR-001, 003–010, 024, 026; AC-02, 03, 05.

## Stage 3 — Motion, calibration and index validation

- Parse x/y/z strings or finite numbers into typed, finite numeric accessors;
  retain source spelling. Reject booleans, null and invalid float tokens.
- Validate positive finite sample rate, nonempty acceleration, equal paired
  lengths, all components, and finite values. Preserve vector objects without
  scientific interpretation.
- Validate start/end bounds and optional marker bounds independently. Do not
  require gravity/incline to follow start.
- Add explicit `inferred sample relative time` utility only if approved by ADR;
  clearly separate from source timestamp metadata.
- **Tests:** all four actual recordings, malformed x/y/z, unequal sequences,
  NaN/Infinity, rate zero, index out-of-range, Taron marker ordering,
  shuffled JSON member order, no source mutations.
- **Exit:** all four vector sequences survive full import; M3 math absent.
- **Trace:** FR-011–016; AC-01, 02, 06.

## Stage 4 — Optional GPS, metadata and attributes

- Parse independently timed GPS fixes, preserve numeric source values,
  precision and GPS accuracy/sentinel evidence. Warn for suspicious/negative
  speed/course/accuracy, without deciding units or sentinel semantics.
- Treat optional weather, park and ride-position metadata as truly optional.
  Preserve arbitrary attribute order, label and values, and unknown keys.
- Define documented partial-optional-GPS behavior: which malformed fixes become
  unavailable with warnings and when core import still succeeds. Do not silently
  remove the original fix from the source envelope.
- **Tests:** complete baseline quartet including missing fields, `-1` GPS
  examples and Taron's two attributes; partial malformed optional fixtures;
  GPS arrays of different lengths and sparse data.
- **Exit:** all four complete originals return usable typed motion recordings
  without invented GPS values, location, temperature or riding position.
- **Trace:** FR-009, 010, 017–022, 025; AC-01, 04, 07.

## Stage 5 — Public integration and resilience

- Finish documented import service contract in `importers`, normalize
  diagnostic exposure, stable API errors and source provenance. Keep UI/stores
  outside M2; optionally supply a non-GUI manual diagnostic invocation for
  developer use without introducing a product export feature.
- Benchmark representative imports locally, state actual observed memory/time
  rather than invented throughput or guaranteed performance.
- Cover concurrency/repeated import if API permits it; verify that no original
  recording is written or normalized.
- **Tests:** integration round trip and deterministic diagnostics, resource
  limits, future unknown key, fixture hashes and import with no network.
- **Exit:** an M4 caller can use the importer without UI dependencies.
- **Trace:** FR-001, 003, 028–030; AC-01, 02, 08.

## Stage 6 — M2 acceptance and review preparation

- Run **all** required local Windows checks in AGENTS.md / development SETUP:
  `uv lock --check`, Ruff lint/format, strict mypy, `npm run typecheck`,
  `npm run test:types`, pytest and `npm run test:docs`.
- Validate all four real fixture hashes and recorded decoded counts.
- Create `docs/validation/M2.md` with date, environment, actual commands,
  outputs, requirements-to-test traceability, unsupported assumptions,
  performance evidence and exact acceptance status AC-01–AC-10.
- Update README, roadmap and documentation navigation **only when behavior
  changes justify it**. Do not mark M2 done prematurely.
- After owner approval for staging/committing/pushing, use an approved branch,
  inspect the staged diff, follow the prescribed commit-header syntax,
  open a **draft** pull request into `main`, and verify actual GitHub Windows
  check and documentation job outcomes.
- Do **not** merge without separate owner authorization.
- **Exit:** all AC-01–AC-10 supported by evidence and no unreviewed scope creep.

## Working acceptance matrix

| Stage | Key requirements                       | Key acceptance criteria |
| ----- | -------------------------------------- | ----------------------- |
| 0     | FR-001, FR-004, FR-007, FR-024, FR-030 | AC-02                   |
| 1     | FR-002–006, FR-023, FR-027             | AC-03, AC-08            |
| 2     | FR-001, FR-003–010, FR-024, FR-026     | AC-02, AC-03, AC-05     |
| 3     | FR-011–016                             | AC-01, AC-02, AC-06     |
| 4     | FR-009–010, FR-017–022, FR-025         | AC-01, AC-04, AC-07     |
| 5     | FR-001, FR-003, FR-028–030             | AC-01, AC-02, AC-08     |
| 6     | All FR/NFR, documented exceptions      | AC-01–AC-10             |

## Operational guardrails

Do not modify or format any `.forces` file. Do not leak full GPS coordinates
into logs or PR text. Do not introduce cloud dependencies, an M3 force
calculation, a GUI import wizard, database storage, timeline/video export
or automated merge. Describe unresolved source semantics explicitly.
