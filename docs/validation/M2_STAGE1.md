# DEV-REQ-002 Stage 1 models — 2026-10-13

Scope: immutable canonical/source models and structured diagnostic/outcome types.
Status: Stage 1 model acceptance and local Windows quality checks verified.
M2 import acceptance remains open.
Branch: `feat/m2-schema-inventory`, continuing related Stage 0 work at
`72b2a183316a8fd1a5018b8c27d0f769df9d3ac9`. No staging, commit, push, merge or
next-stage implementation is authorized by this request. M2 is not complete.

## Implemented boundaries

- `domain/source.py`: owned bytes/provenance, exact SourceNumber tokens and copied,
  recursively immutable object/array trees, including unknown extension fields.
- `domain/models.py`: typed recording, finite vectors, motion, optional GPS slots,
  attributes, metadata, indices, source extrema and explicit default provenance.
- `domain/_validation.py`: runtime checks at annotated dataclass boundaries;
  annotations alone do not prevent incorrectly typed values from being stored.
- `importers/diagnostics.py`: structured severity/code/pointer/message/index and
  stable severity/pointer/code ordering, with stable ties.
- `importers/result.py`: immutable literal-tagged success/failure union,
  consistent recording/error contracts and source provenance accessors.

Public packages re-export these concepts. Neither imports Qt. No file access,
document decoder, schema dispatch, time inference, iOS math, UI, database or
export behavior was added. No dependency or lockfile was added or changed.
See [the model guide](../development/CANONICAL_MODELS.md) for construction,
representation choices and explicit limits of Stage 1 behavior.

## Requirement traceability

| Requirement | Stage 1 implementation/evidence                                                              | Later work                                          |
| ----------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| FR-002      | Typed frozen recording, motion, GPS, attributes, metadata, envelope, diagnostics and results | Instantiate from actual decoded recordings          |
| FR-003      | Tagged results, no error-bearing success or recording-bearing failure; optional provenance   | Import service and supported-version validation     |
| FR-004      | Owned raw byte round trip; deep source copies; exact numeric tokens and unknown fields       | Populate tree from the same bytes in strict decoder |
| FR-005      | Source path is provenance only; model constructors perform no source-file I/O                | Read-only path adapter and later-import checks      |
| FR-006      | Full source tree plus typed indices, vectors, extrema, smoothing, weather and GPS            | Source-field parsing and diagnostic generation      |
| FR-023      | Structured immutable diagnostics, escaped pointers and deterministic ordering                | Generate source-specific parser diagnostics         |
| FR-027      | Mutable byte/tree/sequence/attribute/diagnostic inputs cannot alter constructed objects      | Resilience of complete import pipeline              |

The synthetic in-memory construction exit criterion is verified. AC-03 has model
ownership/type-retention/byte-round-trip evidence; AC-08 has Qt-free typed model
evidence. These do not complete either criterion's later real-import integration.
Owner defaults are represented as effective values with SOURCE/DEFAULT origins;
raw absent properties remain absent. GPS absence, empty sequence and invalid
container are distinct; invalid fix slots remain indexed and negative values survive.

## Focused validation and fixes

Native Windows Python 3.14.6 / uv 0.13.0 and the existing locked quality tools.
All synthetic inputs are created in memory. Temporary type contracts live under
`.tmp/`; tests never write to original recordings.

```powershell
uv run pytest tests/test_source_models.py tests/test_recording_models.py tests/test_import_results.py
uv run mypy src
npm run typecheck -- --outputjson
npm run test:types
```

- 56 focused pytest cases passed on win32 / Python 3.14.6, including a fresh
  subprocess verifying no PySide/PyQt package import.
- mypy checked 15 source files without issues; Pyright analyzed 25 files with
  zero errors/warnings.
- Seven actual Pyright contracts passed: three existing Pydantic cases plus
  literal result-tag narrowing, invalid vector construction, frozen field
  assignment and read-only source mapping mutation. Tests require positive
  analyzed-file counts and exact expected diagnostic rules.
- Initial mypy loop-variable inference conflicts were fixed with distinct names.
  Pyright's strict runtime-guard diagnostics were resolved with explicit object
  boundary checks, without weakening checker configuration.
- The positive API contract initially failed to narrow property/truthiness tags.
  Results now use immutable Literal fields; an explicit `success is True` guard
  narrows the public union. The negative cases assert exactly one intended error,
  including readonly Mapping item assignment.

## Final project verification

All applicable project suites passed with native Windows Python 3.14.6, uv 0.13.0
and the project-pinned Node 26.11.1 / npm 11.20.0 after focused model/API checks.
The independent-length GPS case also passed alone before the final full run.
Installed quality checks ran with npm offline. Ruff retains the owner's COM812
configuration; overlapping long conditions were shortened to satisfy both lint
and format checks. Documentation spelling findings were corrected without
weakening the checks; the pytest filename is allowed locally in this report.

| Exact command                                                | Actual final result                                           |
| ------------------------------------------------------------ | ------------------------------------------------------------- |
| `uv lock --check`                                            | 32 packages; lock consistent                                  |
| `uv run ruff check .`                                        | All checks passed                                             |
| `uv run ruff format --check src tests`                       | 25 files already formatted                                    |
| `uv run mypy src`                                            | 15 source files; no issues                                    |
| `npm run typecheck -- --outputjson`                          | 25 files; zero errors/warnings                                |
| `npm run test:types`                                         | 7 passed (3 Pydantic, 4 canonical contracts)                  |
| `npm run test:dependencies`                                  | 6 passed                                                      |
| `uv run pytest`                                              | 110 passed on win32 / Python 3.14.6, including both GUI cases |
| `npm run test:docs`                                          | 25 Markdown/link tests; CSpell 63 files, zero issues          |
| `.tmp/m1-actionlint/actionlint.exe .github/workflows/ci.yml` | No diagnostics; exit 0                                        |
| `uv run python .tmp/stage1-confirm.py`                       | 5/5 original sizes, SHA-256 and modification times unchanged  |

No source fixture, pinned digest, recursive snapshot, staged entry or Git HEAD
was changed. No GitHub operation was performed. Hosted CI for Stage 1 remains
unverified because publication is not authorized in this request.

<!-- cspell:words conftest -->

## Files changed

New model and test artifacts:

- `src/ride_forces_analyzer/domain/_validation.py`
- `src/ride_forces_analyzer/domain/source.py`
- `src/ride_forces_analyzer/domain/models.py`
- `src/ride_forces_analyzer/importers/diagnostics.py`
- `src/ride_forces_analyzer/importers/result.py`
- `tests/conftest.py`
- `tests/test_source_models.py`
- `tests/test_recording_models.py`
- `tests/test_import_results.py`
- `tests/types/recording.test.mjs`
- `docs/development/CANONICAL_MODELS.md`
- `docs/validation/M2_STAGE1.md`

Adjusted: both domain/importer package `__init__.py` facades; `package.json`
(the type-contract command only); README, documentation index, roadmap,
architecture, ADR 0002, CODE_QUALITY, DEV-REQ-002 and its implementation plan.
AGENTS, all five original recordings, original integrity tests, the recursive
snapshot and both lock files are unchanged. No new dependencies were introduced.

## Integrity and unverified items

Before/after byte count, SHA-256 and modification-time evidence covers all five
original fixtures. Their existing pins and Stage 0 recursive snapshot are not
modified. Model tests consume synthetic data; the regular fixture suite remains
the actual source-integrity boundary.

SourceEnvelope deliberately does not check the correspondence between manually
supplied bytes and tree: that requires Stage 2's decoder. Constructors enforce
typed canonical preconditions rather than parsing source fields. Unsupported
versions, resource limits, optional-field warning generation, actual five-file
imports, device dispatch, Windows performance, hosted CI and interactive editor
behavior remain unverified/unimplemented as applicable. Scientific epochs,
axes, GPS units/sentinels and end-index interpretation remain open.

Frozen objects guard normal mutation, not reflective Python bypasses. Read-only
mappings own their backing storage; no mutable dictionary view escapes. Objects
with mappings are not promised to be hashable or serializable by dataclasses.asdict.
Diagnostic messages require safe caller wording; built-in representations omit
source content and GPS trace fields.

Stage 1 is ready for review; final project checks are recorded above. Stage 2 requires a
separate owner instruction; no decoder or subsequent stage is started here.
