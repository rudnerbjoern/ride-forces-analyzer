# DEV-REQ-003 — Implementation plan

**Status:** Planning only. No scientific analysis implementation authorized.
**Requirements:** [DEV-REQ-003](../../requirements/DEV-REQ-003-scientific-analysis.md).
**Steps for Codex:** [PROMPTS.md](PROMPTS.md).
**Input prerequisite:** Verified M2 canonical importer with provenance and diagnostics.

Each stage is a separate review gate. Perform no stage automatically after another.
Development follows [AGENTS.md](../../../AGENTS.md), including branch, staging,
approval, commit and pull-request rules.

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

**Trace:** SCI-001–010, VAL-007, AC-01 and AC-08.
**Exit:** Written decision matrix with unresolved items and safe defaults.

## Stage 1 — Dependency and scientific API design

Audit existing NumPy/Pandas and proposed SciPy/Pint/GeographicLib for current
Windows/Python 3.14.6 compatibility, licenses, supported versions and lock.
Document rationale for not yet adopting AHRS or pyproj. Define immutable
`AnalysisProfile`, units/frames, capability state, provenance, diagnostics
and `AnalysisResult`; use NumPy arrays with documented read-only ownership.
Avoid Qt or M2 import duplication. Use a separate authorized change for
dependency installation/lock updates when implementation begins.

**Trace:** LIB-001–008, SCI-001–003, RES-001–005, AC-02–03.
**Exit:** Fully typed, testable API shape with approved dependency policy.

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
known geodesic examples, missing fixes and the four original recordings.

**Trace:** GPS-001–010, VAL-005–006, AC-07.
**Exit:** Unit-labeled GPS estimates with coverage and exclusions.

## Stage 6 — Source-app comparison and regression matrix

Build a comparison protocol per fixture: source extrema, selected segment,
rider axis, orientation, smoothing and reference screenshots/values from the
actual Ride Forces application, if supplied. Report numerical differences
only when comparing like-with-like; otherwise document UNKNOWN.
Avoid reverse-engineering claims based only on coincidence of extrema.
Regression test all four immutable fixtures and synthetic baseline datasets.

**Trace:** VAL-006–008, AC-04–09.
**Exit:** Repeatable discrepancy report and labeled limitations.

## Stage 7 — Integration, review and acceptance

Expose a pure-analysis API usable later by M4–M7; keep it independent of UI,
storage and encoder. Benchmark and profile representative data, report real
measurements with actual environment. Run all AGENTS.md commands:
`uv lock --check`, Ruff lint and format, mypy, `npm run typecheck`,
`npm run test:types`, `npm run test:dependencies`, pytest and
`npm run test:docs`. Create `docs/validation/M3.md` with each AC's evidence
and unresolved items. Update roadmap only with verified results. Prepare a
draft PR to main only with owner authorization; review actual Windows CI,
never merge without separate owner approval.

**Trace:** All LIB/SCI/SIG/GPS/RES/VAL, AC-01–10.
**Exit:** Complete acceptance evidence or M3 remains open.

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
