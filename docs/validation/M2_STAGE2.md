# DEV-REQ-002 Stage 2 decoding — 2026-10-13

Branch: feat/m2-schema-inventory; Git baseline 07b7c55.
Scope: strict source decoding only, including required schema shapes. Existing
AGENTS/workflow and Stage 3 changes were preserved. No staging, commit, push,
PR, merge or next-stage implementation was performed.

## Requirements and files

- FR-001: public pure bytes API and separate bounded read-only Path adapter.
- FR-003: stage-specific tagged DecodeResult with diagnostics/version/provenance;
  complete ImportResult/Recording integration remains planned.
- FR-004–006: exact retained bytes and immutable complete tree, original tokens,
  indices, vectors, extrema, GPS and optional metadata; no writes/default insertion.
- FR-007: explicit adapter dispatch for literal 2.2.0 only, with structured errors.
- FR-008: required core field/component shapes; no universal gravity/GPS requirement.
  Full measured validity/device capabilities belong to motion/integration stages.
- FR-009–010: optional/unknown data, nulls and absence survive; typed optional
  metadata/default application remains Stage 4/integration work.
- FR-024: strict UTF-8/JSON, all-depth duplicate rejection, object root, configurable
  preflight budgets, safe path/number/runtime failures and deterministic first error.
- FR-026: offline bytes decoding and local regular-file reads; no embedded URL
  fetching or diagnostic payload dumps. No Qt dependency was introduced.

New: `src/ride_forces_analyzer/importers/decoder.py`, `limits.py`,
`_json_preflight.py`, `tests/test_decoder.py`,
`docs/development/STRICT_DECODING.md`, `docs/validation/M2_STAGE2.md`.
Updated: importer exports, the existing Pyright contracts, README/docs index,
roadmap, architecture, ADR 0002, requirements, plan and relevant development guides.
Stage 3's dated report gains a follow-up link; its historical evidence is preserved.
Original fixtures/pins/snapshot, domain models, Motion parser, dependencies, lock
files and UI were not changed. Existing AGENTS edits remain untouched.

## Focused evidence

Native Windows Python 3.14.6 / uv; original source bytes remain read-only.
`uv run pytest tests/test_decoder.py`: initial 176 passed before adding read/depth
edge cases. `uv run pytest tests/test_decoder.py tests/test_project.py`: 189 passed
(182 decoder + 7 existing project/integrity cases) after those additions.
The additional bytes-only offline case passed alone (1 passed), making 183 decoder
cases for final validation. These focused runs preceded formatting-only corrections
and the final chunk-size cap; the final full suite reran every decoder case afterward.

## Final project checks

Native Windows: Python 3.14.6, uv 0.13.0, PySide6/Qt 6.12.0,
Node 26.11.1 / npm 11.20.0 and Pyright 1.1.414. Installed Node checks ran offline.
Lock results were reused after a formatting correction because dependency/lock
inputs remained unchanged. All Python/typing checks below passed before the final
documentation correction and spelling-only comments; executable Python is unchanged.

- `uv lock --check`: 32 packages resolved; lock consistent.
- `uv run ruff check .`: all checks passed.
- `uv run ruff format --check src tests`: 31 files already formatted.
- `uv run mypy src`: 19 source files, no issues.
- `npm run typecheck -- --outputjson`: 31 analyzed files, no errors/warnings.
- `npm run test:types`: 9 passed, including decoder/motion outcome narrowing.
- `npm run test:dependencies`: 6 passed.
- `uv run pytest`: 546 passed on win32; 183 decoder cases, the existing motion,
  source/inventory/model checks and both native GUI cases all passed.
- `npm run test:docs`: 29 documentation/link tests passed; markdownlint found
  no issues and CSpell checked 73 files with zero issues.

Local CSpell annotations allow required API/Unicode names, the JSON escape-letter
set and deliberately malformed test input only in the relevant files. No lint,
type or spelling check was disabled. Missing COM812 commas were corrected without
changing the owner's rule configuration. `git diff --check` passed.

## Acceptance and limits

All five real originals are decoded through Path and bytes APIs with complete
source retention. Tests check pinned byte count/SHA-256, before/after bytes and
modification times, immutable source access and deterministic results. All GPS
data remain present without scientific interpretation or full trace output.

The malformed-input decoder exit is verified by focused negative tests. AC-02/03
have decoder evidence; AC-05 has the decoding/schema/resource portion only.
Motion numeric validity/bounds are separate and were not integrated in this stage.
AC-01/04/07/08 complete-import behavior and M2 completion remain open.

Resource limits follow ADR 0002, with explicit positive machine-sized integer
configuration and a supported depth ceiling of 128. Tests prove preflight rejection
before full tree allocation. Diagnostic-budget enforcement is currently inherent
in fail-fast output (one record); aggregate combined-pipeline enforcement is future work.

Actual denied Windows ACLs, filesystem race attacks, mapped-drive locality,
peak memory/timing benchmarks, hosted CI and fresh interactive editor behavior
are unverified. I/O failures and short/growing/changed handles are covered with
controlled mocks. GPS/time/axes/units/end-index semantics remain open.
The decoded source boundary is ready for separately authorized integration with
motion and optional metadata stages. Stop after this stage.
