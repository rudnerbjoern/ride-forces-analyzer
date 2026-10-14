# DEV-REQ-003 — Implementation plan

<!-- cspell:words AHRS stationarity Butterworth Goldens orthonormality acausal Missingness sosfiltfilt basemaps -->

**Status:** Stage 0 scientific policy proposed; Stage 1 model contracts implemented
with separate owner authorization. Stage 2 implements device-only norms and
explicit Pint conversion; calibrated analysis remains planned.
**Requirements:** [DEV-REQ-003](../../requirements/DEV-REQ-003-scientific-analysis.md).
**Steps for Codex:** [PROMPTS.md](PROMPTS.md).
**Input prerequisite:** Verified M2 canonical importer with provenance and diagnostics.
**Architecture:** [arc42 index](../../architecture/README.md); the twelve chapters
are the sole maintained architecture views. Apply ARC-001–004 from the requirements.
**Fixtures:** All five [authorized recordings](../../development/RECORDINGS.md).

Each stage is a separate review gate. Perform no stage automatically after another.
Development follows [AGENTS.md](../../../AGENTS.md), including branch, staging,
approval, commit and pull-request rules.

## Architecture maintenance across stages

Read the index and stage-relevant chapters once per working context. Update only
affected architecture views; retain unchanged evidence and clearly mark proposals,
implemented behavior and scientific unknowns. Use Mermaid for applicable diagrams
and check changed definitions locally. Link ADRs from chapter 09; never revive
the removed overview or copy stage instructions into architecture/AGENTS.md.

| Stage | Primary arc42 views to read/update when affected                                                                                                                                                                                                            |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0     | [08 Concepts](../../architecture/08_concepts.md), [09 Decisions](../../architecture/09_architecture_decisions.md), [11 Risks](../../architecture/11_technical_risks.md)                                                                                     |
| 1     | [02 Constraints](../../architecture/02_architecture_constraints.md), [04 Strategy](../../architecture/04_solution_strategy.md), [05 Blocks](../../architecture/05_building_block_view.md), [07 Deployment](../../architecture/07_deployment_view.md), 08/09 |
| 2     | 05, [06 Runtime](../../architecture/06_runtime_view.md), 08, [10 Quality](../../architecture/10_quality_requirements.md)                                                                                                                                    |
| 3     | 05/06/08/09/10/11                                                                                                                                                                                                                                           |
| 4     | 05/06/08/10/11                                                                                                                                                                                                                                              |
| 5     | 05/06/08/10/11                                                                                                                                                                                                                                              |
| 6     | 08/09/10/11                                                                                                                                                                                                                                                 |
| 7     | Review all twelve chapters and [12 Glossary](../../architecture/12_glossary.md); update every view affected by the verified implementation                                                                                                                  |

Changes to goals or external scope also update chapters 01/03. This table maps
existing stage work to documentation; it does not authorize an implementation stage.

## Stage 0 — Scientific feasibility and decisions

Inspect the current M2 domain/public API, real recordings and source-app references.
Capture separate known facts, assumptions and unresolved questions concerning
proper acceleration versus gravity-compensated acceleration, measurement units,
axes, frame transform, timestamps, GPS sentinel handling and extrema. Provide
an ADR specifying measurement nomenclature and a **capability gate**:
device-only results allowed without calibrated rider-frame proof;
definitive rider-axis output forbidden without independent evidence.
Specify reference-data collection against the source app without claiming its
private algorithms. Review with owner before any rider-force interpretation.
Link the proposed scientific ADR from chapter 09 and record the decision/evidence
state in chapters 08/11; do not label unknowns verified during documentation work.

**Trace:** SCI-001–010, VAL-007, AC-01 and AC-08.
**Exit:** Written decision matrix with unresolved items and safe defaults.

**Stage 0 review artifact:** [ADR 0003](../../decisions/0003-scientific-semantics-and-capability-gates.md)
is proposed, with source observations, API/reference limits, per-channel gates and
a reference-collection protocol. Chapters 08/09/11 retain the proposal and open
evidence. Owner ADR review, source-app comparison and scientific qualification
remain pending; AC-01/AC-08 and M3 are not fully accepted. Stage 0 did not start
Stage 1 automatically; its later separate authorization is recorded below.

Native Windows input verification on 2026-10-14, at code revision
`0db96029c724edccb8175c7843bf8f18be3b808d`:

```powershell
uv run --locked pytest tests/test_import_service.py tests/test_fixture_inventory.py tests/test_project.py tests/test_recording_models.py tests/test_source_models.py tests/test_import_results.py
```

Result: **131 passed in 17.31 s**, Python 3.14.6 / pytest 9.1.1. The public Path/bytes
service preserves all five originals and typed/source distinctions; fixture tests
match pinned byte lengths/SHA-256 and preserve modification times. Source inspection
also checked every GPS slot's flagged values and numerical timestamp ordering
without assigning units or epochs. Temporary inspection output remains under `.tmp/`.
Applicable final checks are `npm run test:docs`, local Mermaid syntax validation
and `git diff --check`; none establishes scientific or app-equivalence acceptance.
Application/dependency/lock files remain unchanged; this stage adds no scientific
test implementation because it introduces no executable scientific behavior.

Local syntax command:

```powershell
.tmp/node-v26.11.1-win-x64/node.exe .tmp/validate-arc42.mjs
```

Result: **7 Mermaid definitions passed**, including the proposed gate in chapter 08,
using the existing temporary Mermaid 12.2.0 installation. Syntax only; visual layout
and GitHub rendering were not tested. `git diff --check` passed. The first final
documentation run passed Markdownlint for 50 files but CSpell flagged the valid
technical term `orthonormality`; the ADR now declares that word locally, as the
requirements already do. No lint rule, dictionary configuration or dependency changed.

After correction, `npm run test:docs` passed **50 local-link tests**, with
Markdownlint **50 files / 0 issues** and CSpell **108 files / 0 issues**.
Read-only Path/bytes inspection before/after documentation changes also matched
all five pinned byte lengths/SHA-256 and baseline modification times; source
extrema tokens and GPS warnings were inspected without changing any fixture.
The final documentation edit receives the same suite; M2/API tests are not
repeated for that unchanged executable/fixture scope. Stage 0 is ready for owner
review, with policy approval and scientific references still open.

## Stage 1 — Dependency and scientific API design

Audit existing NumPy/Pandas and proposed SciPy/Pint/GeographicLib for current
Windows/Python 3.14.6 compatibility, licenses, supported versions and lock.
Document rationale for not yet adopting AHRS or pyproj. Define immutable
`AnalysisProfile`, units/frames, capability state, provenance, diagnostics
and `AnalysisResult`; use NumPy arrays with documented read-only ownership.
Avoid Qt or M2 import duplication. Use a separate authorized change for
dependency installation/lock updates when implementation begins.
Update planned library/API boundaries and deployment implications in the relevant
arc42 chapters; dependency installation and scientific design retain separate gates.

**Trace:** LIB-001–008, SCI-001–003, RES-001–005, AC-02–03.
**Exit:** Fully typed, testable API shape with approved dependency policy.

**Stage 1 implementation:** The owner explicitly selected executable model contracts
with tests. [ADR 0004](../../decisions/0004-analysis-contracts-and-library-policy.md)
records the library/license/lock audit and API decisions; the
[model guide](../../development/ANALYSIS_MODELS.md) describes implemented contracts.
NumPy 2.5.4 remains the project lock choice. SciPy 1.18.1, Pint 0.26.1 and
GeographicLib 2.1 were jointly audited in a separate exact-version Windows
Python 3.14.6 environment, with Pandas 3.0.6 as an optional adapter; eight synthetic
library smoke checks passed. AHRS/pyproj were not installed. Root dependency/lock
adoption, owner policy review, scientific references and numerical services remain
open. AC-02/AC-03 are not complete M3 acceptance.

At the Stage 1 exit, no Stage 2 work was started. Its subsequent separate owner
instruction authorizes NumPy norms and explicit Pint conversion, with the required
Pint analysis-extra/lock adoption. Synthetic audit conversions alone were not
production Ride Forces calculations.

Native Windows verification on 2026-10-14 (Python 3.14.6, NumPy 2.5.4; base revision
`0db96029c724edccb8175c7843bf8f18be3b808d` plus the Stage 1 working-tree contracts):

| Command                                                                                                     | Actual result                                                                     |
| ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `uv lock --check`                                                                                           | Consistent unchanged root lock; 32 packages                                       |
| `uv run --locked pytest tests/test_import_service.py tests/test_project.py`                                 | M2 prerequisite: 61 passed in 14.42 s before model coding                         |
| `uv lock --project .tmp/m3-stage1-audit --python 3.14.6`                                                    | Separate exact-version audit lock: 13 packages                                    |
| `uv sync --project .tmp/m3-stage1-audit --python 3.14.6 --locked --no-build`                                | 12 distributions installed from wheels in the isolated audit environment          |
| `.tmp/m3-stage1-audit/.venv/Scripts/python.exe .tmp/m3-stage1-audit-smoke.py`                               | 8 synthetic upstream API checks passed; no original recording interpretation      |
| `uv run --locked pytest -o cache_dir=.tmp/pytest-cache tests/test_analysis_models.py`                       | 29 focused cases passed before adding the final offline case                      |
| `uv run --locked pytest -o cache_dir=.tmp/pytest-cache tests/test_analysis_models.py -k model_construction` | New final offline case: 1 passed, 29 deselected                                   |
| `uv run --locked ruff check .`                                                                              | Passed for final code                                                             |
| `uv run --locked ruff format --check src tests`                                                             | 39 files formatted; passed                                                        |
| `uv run --locked mypy src`                                                                                  | No issues in 23 source files; reused after later test/documentation-only edits    |
| `npm run typecheck`                                                                                         | 0 errors/warnings for final source and tests                                      |
| `npm run test:types`                                                                                        | 11 passed                                                                         |
| `npm run test:dependencies`                                                                                 | 15 passed                                                                         |
| `node --test tests/ci/changes.test.mjs`                                                                     | 40 passed                                                                         |
| `uv run --locked pytest -o cache_dir=.tmp/pytest-cache`                                                     | 866 passed in 39.13 s, including all 30 analysis cases and native GUI regressions |
| `.tmp/node-v26.11.1-win-x64/node.exe .tmp/validate-arc42.mjs`                                               | All 7 definitions passed; no visual rendering verification                        |

Initial failures were corrected without weakening settings: COM812 missing commas,
strict typing of runtime checks/default mapping/optional samples, and documented
NumPy metadata-mutation deprecation in a deliberate adversarial test. CSpell then
flagged new legitimate library/API names; the project dictionary now records those
specific names, while less clear wording was replaced. Final documentation checks
passed: `npm run test:docs` verified **52 local-link cases**, Markdownlint
**52 files / 0 issues** and CSpell **112 files / 0 issues**. The recorded final
documentation edit receives the same suite; unchanged executable checks are reused.
`git diff --check` passed. Final read-only fixture inspection matched all five
pinned byte lengths/SHA-256 and baseline modification times; M2 and analysis tests
also retain exact bytes before/after use. No numerical worker, project dependency/
lock change or Git mutation is part of Stage 1. Scientific qualification and
hosted CI remain open.

## Stage 2 — Device-frame vectors and units

Implement NumPy norms and basic device-frame vector operations.
Introduce Pint-based boundary conversions and distinct proper acceleration,
gravity and kinematic-acceleration quantity types. Never combine the exported
sequences until upstream semantics are validated. Keep missing/unit-unknown
channels unavailable rather than assigning 1 g or zero as a source fact.
Synthetic stationarity and free-fall-like examples must carry their explicit
simulated sensor convention and not be treated as proof for real files.

**Trace:** SCI-004–006, SCI-010–012, VAL-001, VAL-004, AC-04, AC-06.
**Exit:** Analytically verified device-only capability and provenance.

**Stage 2 implementation:** Separately instructed on 2026-10-14, on the existing
`docs/github-templates` feature branch, base revision
`0db96029c724edccb8175c7843bf8f18be3b808d` plus the preserved Stage 0/1 working tree.
The verified M2 service/model APIs remain unchanged; their passing Stage 1
prerequisite evidence was reused before coding and all importer/fixture suites
were included in final Windows validation after Pint adoption.

`analysis.device` now provides source-bound MotionUnitContract declarations,
explicit Pint SI conversion, stable NumPy DEVICE vector norms and independent
acceleration/gravity outcomes in immutable AnalysisResult. Pint 0.26.1 is adopted
in the optional analysis extra and root uv lock; its audited transitive packages
are flexcache 0.3, flexparser 0.4 and platformdirs 4.13.0, with the existing
snapshot of typing-extensions. Other audited scientific packages remain deferred.
The `device_vectors` profile stores original units, quantity meaning and library
versions; source and algorithm provenance, caller UTC calculation time, references
and independent sample indices remain retained. No source relationship is inferred.

Synthetic tests explicitly declare their sensor convention. Stationary specific
force +g0 z and independent gravity -g0 z each have magnitude g0; zero specific
force remains valid zero. SI, centimeters/s², feet/s² and standard_gravity convert
explicitly to SI. Unsupported units, bare `g`, absent references and wrong source/
sequence bindings are rejected. Missing/unknown channels remain UNAVAILABLE with
ordered warnings; float64 range failures produce INVALID products and errors.
Stable norms avoid intermediate squaring overflow/underflow; exact precision stays
in original M2 bytes. Norm overflow retains independently usable vectors.

Native Windows Python 3.14.6 / NumPy 2.5.4 / Pint 0.26.1 results for the final
Stage 2 code/configuration (all commands from the repository root):

| Command                                                                                                             | Actual result                                                                                   |
| ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `uv add --optional analysis pint==0.26.1 --no-sync`                                                                 | Required manifest/lock adoption; 36 packages resolved, existing versions retained               |
| `uv sync --locked --all-extras --group dev --no-build`                                                              | Pint and three new transitive distributions installed; local editable project rebuilt           |
| `uv run --locked pytest -o cache_dir=.tmp/pytest-cache tests/test_device_analysis.py tests/test_analysis_models.py` | 59 passed in 6.15 s; 29 device and 30 model cases                                               |
| `uv lock --check`                                                                                                   | Consistent lock; 36 packages                                                                    |
| `uv run --locked ruff check .`                                                                                      | Passed                                                                                          |
| `uv run --locked ruff format --check src tests`                                                                     | Passed; 41 files already formatted                                                              |
| `uv run --locked mypy src`                                                                                          | No issues in 24 source files; source unchanged after this result                                |
| `npm run typecheck`                                                                                                 | 0 errors/warnings for final source/tests                                                        |
| `npm run test:types`                                                                                                | 11 passed                                                                                       |
| `npm run test:dependencies`                                                                                         | 15 passed                                                                                       |
| `node --test tests/ci/changes.test.mjs`                                                                             | 40 passed                                                                                       |
| `uv run --locked pytest -o cache_dir=.tmp/pytest-cache`                                                             | 895 passed in 41.31 s, including device/model, M2, integrity and native GUI tests               |
| `npm run test:docs`                                                                                                 | 52 local-link tests passed; Markdownlint 52 files / 0 issues; CSpell 114 files / 0 issues       |
| `.tmp/node-v26.11.1-win-x64/node.exe .tmp/validate-arc42.mjs`                                                       | 8 Mermaid definitions passed syntax checks; visual layout/hosted rendering unverified           |
| `uv run --locked python .tmp/inspect-m3-evidence.py`                                                                | All five pinned byte lengths, SHA-256 digests and Stage 0 baseline modification times unchanged |

Temporary runners/caches/evidence remain under `.tmp/`. Final documentation receives
`npm run test:docs` and `git diff --check` after this evidence is recorded; unchanged
application checks are not repeated for documentation-only edits. The separate
Git-delivery skill suite is unaffected and was not run. No hosted CI result is
claimed for these unpublished changes.

Initial failures were corrected without weakening checks: fixture parametrization
used the filename mapping incorrectly; mypy required an explicitly typed sample buffer;
COM812/formatting required final normalization; Markdown spacing/tables needed aligned
padding and CSpell needed legitimate library/API terms. A new Mermaid message
used a statement-separator semicolon; replacing it with plain text fixed parsing. The final checks above
pass; scientific unknowns remain open, not waived by green tooling.

Architecture updates cover chapters 02/04/05/06/07/08/10 and the glossary/index.
Existing ADR 0004 was extended and remains linked from chapter 09; ADR 0003 and
chapter 11 keep source units, axes, yaw, epochs, GPS units/sentinels and source-app
reference evidence unresolved. ARC-001–003 have stage-specific structure,
consistency and syntax evidence; ARC-004 remains open for complete M3 acceptance.
SCI-004–006 and SCI-010–012, VAL-001/004 are covered in this device-only scope;
AC-04/AC-06 have partial evidence only. No projection, rider G, gravity compensation,
filtering, GPS computation, library UI, export or release feature was implemented.

All five originals, including Iron Gwazi without gravity/GPS, remain unit-unqualified:
no current real fixture is assigned a physical unit or calculated norm. References
are caller attestations; contract validation is not empirical certification.
The device-only implementation is ready for owner review. A later stage needs a
new instruction, its own dependency adoption where applicable and independent
scientific qualification; Stage 3 was not started and M3 remains open.

## Stage 3 — Coordinate frames and calibration

Design orthonormal frame checks, determinant/handedness tests, clear active
versus passive rotation convention and inverse transform tests. Use
`scipy.spatial.transform.Rotation` where justified. Check source direction
vectors for validity, preserve originals, and reject invalid frame construction.
Use synthetic axis-aligned and inverted rider configurations. Defer confirmed
rider-frame outputs until the source axis mapping has independent reference
evidence; otherwise return PROVISIONAL or UNAVAILABLE.

**Trace:** SCI-003, SCI-007–009, VAL-001–002, AC-01, AC-04.
**Exit:** Correct tested math plus enforced scientific capability gate.

## Stage 4 — Filtering, events and statistical features

Implement raw/unfiltered baseline, configurable SciPy Butterworth SOS offline
zero-phase filtering, edge/short-segment handling, peak/trough and threshold
selection and defined summary statistics. Add optional identified filters only
when requirements justify them. Record raw-versus-filtered provenance,
cutoffs, order, sampling rate, edge policy and effect on extrema.
Add explicit interpolation policy only as a reusable mathematics primitive,
not playback UI. Test impulse, step, sine, constant and edge behavior.

**Trace:** SIG-001–010, VAL-003, AC-05.
**Exit:** Deterministic, interpretable time-series products.

## Stage 5 — GPS quality and WGS84 geodesics

Implement GeographicLib WGS84 inverse geodesics, accepted-fix quality policy,
segment classification, reported-versus-derived speed and uncertainty flags.
Handle invalid coordinates, negative apparent sentinels and non-monotonic or
unverified timestamps explicitly. Do not equate horizontal path length to rail
length, infer full speed without time validation, interpolate across gaps or
automatically merge GPS and acceleration time bases. Test identical locations,
known geodesic examples, missing fixes and all five originals. Validate actual
GPS segments on the four iPhone profiles and unavailable GPS/gravity-derived
products on Iron Gwazi; never fabricate missing sensor data.

**Trace:** GPS-001–010, VAL-005–006, AC-07.
**Exit:** Unit-labeled GPS estimates with coverage and exclusions.

## Stage 6 — Source-app comparison and regression matrix

Build a comparison protocol per fixture: source extrema, selected segment,
rider axis, orientation, smoothing and reference screenshots/values from the
actual Ride Forces application, if supplied. Report numerical differences
only when comparing like-with-like; otherwise document UNKNOWN.
Avoid reverse-engineering claims based only on coincidence of extrema.
Regression test all five immutable fixtures and synthetic baseline datasets,
with explicit device capabilities and absent-data results.

**Trace:** VAL-006–008, AC-04–09.
**Exit:** Repeatable discrepancy report and labeled limitations.

## Stage 7 — Integration, review and acceptance

Expose a pure-analysis API usable later by M4–M7; keep it independent of UI,
storage and encoder. Benchmark and profile representative data, report real
measurements with actual environment. Run all AGENTS.md commands:
`uv lock --check`, Ruff lint and format, mypy, `npm run typecheck`,
`npm run test:types`, `npm run test:dependencies`, pytest and
`npm run test:docs`. Create `docs/validation/M3.md` with each AC's evidence
and unresolved items. Complete acceptance locally and finalize the report and
verified roadmap status, including all affected arc42 views and Mermaid diagrams;
verify ARC-001–004 and recheck documentation/diagram syntax after final edits. Every acceptance
criterion must have local evidence, including owner acceptance of any permitted
scientific capability exclusion. Missing evidence leaves M3 open.

Required order for final M3 delivery:

1. Finish local Windows acceptance, final arc42/validation documentation and affected checks.
   Stop with the final local result ready for owner review.
2. Only after explicit authorization: stage, commit, push and create the draft PR
   to `main`. The initial delivery must already contain the final acceptance report
   and verified milestone status; never defer either until after draft-PR creation.
3. Use Windows CI as secondary validation. Record actual outcomes in PR metadata
   without a completion-only commit. Selected suites and the final `check` gate
   must pass before a separately
   authorized merge; correct acceptance evidence invalidated by defects.

**Trace:** All LIB/SCI/SIG/GPS/RES/VAL/ARC, AC-01–10.
**Local exit:** All AC-01–AC-10 verified and final documentation checked before
staging, committing, pushing or creating the final draft PR; otherwise M3 remains open.

## Cross-stage test strategy

- Goldens: analytically calculated synthetic vectors, known WGS84 geodesics,
  deterministic filtering sequences, units and sample-rate counterexamples.
- Differential: known input/output from upstream Ride Forces UI only where
  original algorithm, segment, axis and smoothing are sufficiently known.
- Property-based: transformations conserve vector magnitude under valid
  rotations, identity/inverse maps round-trip, finite valid unit conversions.
- Invalid: gaps, false unit assignments, invalid vector basis, bad coordinates,
  insufficient filter length, duplicate/non-monotonic timestamps.
- Provenance: immutable M2 original SHA-256 for every fixture, source data not
  overwritten, no silent fallback from VERIFIED to PROVISIONAL.
- Performance: use actual fixtures; record timing, memory and platform rather
  than adopting unsupported throughput guarantees.

## Gate for next milestone

M3 is scientifically complete only if baseline device-frame and GPS products
are fully tested and definitive rider-frame products are independently
validated or formally excluded from the available capability set with the
owner accepting that limitation. Do not silently claim physical correctness.
