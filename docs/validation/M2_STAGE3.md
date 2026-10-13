# DEV-REQ-002 Stage 3 motion subset — 2026-10-13

Branch: feat/m2-schema-inventory; baseline commit 07b7c55.
Follow-up: [Stage 2](M2_STAGE2.md) was subsequently implemented in a separate
instruction. References to missing decoding below describe the Stage 3 execution
state; complete importer/optional-data integration remains open.
Scope: FR-011–016 only, over immutable source envelopes. Existing uncommitted
agent/workflow documentation changes were preserved. No staging, commit, push,
PR, merge or later-stage work is authorized or performed.

## Implementation and traceability

- FR-011: finite ASCII decimal string/SourceNumber conversion; every x/y/z
  is checked. Original strings/tokens and unknown fields survive in the envelope.
- FR-012: positive finite present rate with SOURCE provenance; owner rate 50
  with DEFAULT provenance only for an absent property. Invalid presence fails.
- FR-013: nonempty acceleration, fully valid supplied gravity, fatal paired-length
  mismatch, no shortening, padding or invented gravity. Apple Watch absence is normal.
- FR-014: required integer-valued JSON start/end indices, individual acceleration
  bounds and start <= end, without slicing or end-index interpretation.
- FR-015: independently bounded optional gravity/incline markers; Taron retains
  gravityIndex=1513 before startIndex=2284, and Iron Gwazi retains gravityIndex
  without a gravity sequence. No marker chronology is assumed.
- FR-016: optional structural vectors warn/become unavailable on defects, while
  valid sibling accessors and all raw content survive. No rider G calculations.

New implementation: `src/ride_forces_analyzer/importers/motion.py`; exports in
the existing importer facade. New runtime tests: `tests/test_motion_parser.py`.
The existing Pyright suite adds a motion-specific result narrowing contract.
[API guide](../development/MOTION_PARSING.md) and
[ADR 0002](../decisions/0002-forces-source-contract.md) record policies and boundaries.
README, docs index, roadmap, architecture, canonical/quality guides, requirements
and implementation plan now distinguish this subset from the full importer.
No dependencies, lock files, domain models, UI or fixtures were changed.

## Evidence

Focused command: `uv run pytest tests/test_motion_parser.py tests/test_project.py`.
Actual result: 260 passed (253 motion cases plus 7 existing project/integrity cases)
on win32 / Python 3.14.6, using PySide6/Qt 6.12.0. This focused run preceded final
formatting-only changes; the final full suite reran all 253 motion cases afterward.
The initial 242 motion tests passed on win32 / Python 3.14.6 before adding final-slot,
Apple Watch supplied-gravity and endpoint cases. A mypy scalar-union annotation
finding was corrected without changing conversion behavior or checker settings.
COM812 trailing commas were corrected in the two new Python files using the
configured formatter; documentation spelling was corrected without weakening checks.

Final native Windows evidence, with uv 0.13.0, Python 3.14.6, Pyright 1.1.414,
Node 26.11.1 / npm 11.20.0, and offline npm checks:

- `uv lock --check`: 32 packages resolved; lock consistent. The passing result
  was reused because dependencies, environment and lock files did not change.
- `uv run ruff check .`: all checks passed.
- `uv run ruff format --check src tests`: 27 files already formatted.
- `uv run mypy src`: 16 source files, no issues. The passing result was reused
  in the remaining quality run; no Python changes followed it.
- `npm run typecheck -- --outputjson`: 27 analyzed files, zero errors/warnings.
- `npm run test:types`: 8 passed, including the motion result narrowing contract.
- `npm run test:dependencies`: 6 passed.
- `uv run pytest`: 363 passed on win32, including both native GUI cases and
  unchanged source/inventory/model regression suites.
- `npm run test:docs`: 27 documentation/link tests passed; markdownlint found
  no issues, and CSpell checked 67 files with zero issues.

## Files changed in this stage

- New: `src/ride_forces_analyzer/importers/motion.py`, `tests/test_motion_parser.py`,
  `docs/development/MOTION_PARSING.md`, `docs/validation/M2_STAGE3.md`.
- Updated: `src/ride_forces_analyzer/importers/__init__.py`,
  `tests/types/recording.test.mjs`, `README.md`, `docs/README.md`, `docs/ROADMAP.md`,
  `docs/architecture/OVERVIEW.md`, `docs/decisions/0002-forces-source-contract.md`,
  `docs/development/CANONICAL_MODELS.md`, `docs/development/CODE_QUALITY.md`,
  `docs/requirements/DEV-REQ-002-forces-importer.md`,
  `docs/implementation/DEV-REQ-002/PLAN.md`.
- Existing AGENTS edits were not modified. Existing CODE_QUALITY workflow rules
  were preserved; only the motion-test coverage entry was added there.

## Integrity and remaining acceptance

Every real-fixture test checks pinned SHA-256/byte length, retains exact source
bytes and checks file bytes/modification time after parsing. Every original
acceleration/gravity component and each of the six structural vectors is compared
with its typed accessor, across all five fixtures. The expected aggregate is
48,029 acceleration and 39,317 gravity vectors; no prefix-only sampling is used.
All GPS bytes and metadata remain present in the source envelope without parsing.

The fixture JSON adapter is test-only, using SourceNumber hooks for the trusted
corpus. Production Stage 2 UTF-8/JSON decoding, dispatch, document limits and
bytes/tree correspondence checks remain unimplemented. Synthetic trees are
manually supplied and do not establish a production document-decoder contract.
MotionParseSuccess is explicitly a validated subset, never a full Recording.

AC-06 and the motion portion of AC-02/03/08/09 receive evidence in this stage.
AC-01 and the Stage 3 full-import exit remain open pending decoder and optional
data/integration stages. Hosted CI, fresh editor inspection and performance/RAM
measurements are unverified. GPS/time/axis/unit/end-index semantics remain open.
This is not M2 completion. The motion boundary is ready for future authorized
decoder/integration work; stop here and obtain a separate instruction for it.
