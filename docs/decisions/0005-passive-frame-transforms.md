# ADR 0005 — Passive frame transforms and exploratory rider gate

<!-- cspell:words orthonormal orthogonalization -->

Status: Implemented numerical convention; general physical source mapping remains open.
This decides numerical conventions and restrictions only. It does not accept the
source-semantic proposals in [ADR 0003](0003-scientific-semantics-and-capability-gates.md)
or qualify any real recording. Trace: SCI-003/007–009, VAL-001–002, AC-01/04 and ARC-001–004.

## Evidence and decision

The reviewed [Ride Forces editing guide](https://rideforces.com/guides/editing/)
says calibration uses selected ride points and graph selection affects statistics.
Its [force guide](https://rideforces.com/guides/understanding-forces/) describes
three directions but supplies no version-matched JSON-axis/sign/export mapping.
These pages were checked on 2026-10-17. No source-app screenshots, exporter mapping
or controlled mounting references are present for the five originals. Scientific
qualification remains open; public descriptions cannot substitute for those references.

Use explicit right-handed orthonormal bases, with target axes stored as rows in
DEVICE coordinates. Passive conversion is `v_target = R @ v_device`, or
`rows @ R.T` for row-array samples. Inverse conversion uses the transpose/inverse.
This is component conversion, distinct from physically rotating the sensor.
Synthetic RIDER axes are X forward, Y left and Z rider-up. DEVICE preserves source
order; WORLD/GRAVITY heading and all physical source mappings remain unresolved.
Do not construct missing axes or orientation from gravity alone.

`OrthonormalFrame` rejects non-unit, skewed, parallel, degenerate and reflected
bases. Admission uses absolute tolerance `1e-10`, relative tolerance zero, on
`R @ R.T = I` and determinant +1. This is a numerical float64 admission threshold,
not a measured source-calibration uncertainty. Inputs are never normalized or repaired.
The [SciPy from_matrix contract](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.from_matrix.html)
otherwise permits orthogonalization: validate first, then use `assume_valid=True`.
[Rotation.apply](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.apply.html)
performs the declared multiplication, with explicit inverse selection. SciPy's
quaternion representation may introduce rounding within the admitted tolerance;
there is no claim of bitwise retention of an approximate matrix in computed output.

## API and capability gate

Opt-in `analysis.frames` exposes OrthonormalFrame, rotate_vectors,
RiderCalibration and analyze_rider_frame. No SciPy types leak through the public
API; a small Protocol adapter covers the dynamically imported upstream interface.
Missing rows remain NaN/false; valid zero stays zero. Overflow produces invalid
products, never zero padding. Source bytes, vectors, markers, units and clocks stay unchanged.

RiderCalibration binds an explicit basis and nonempty references to one source
SHA-256. An available result additionally requires a matching motion unit/quantity
contract and a rider_calibrated AnalysisProfile with allow_provisional, named
assumptions and policy references. It is always PROVISIONAL, never VERIFIED rider
loading. No calibration means UNAVAILABLE; absent/unqualified motion retains its
independent exclusion. Wrong caller types/source bindings or missing opt-in raise;
calculation range defects become INVALID channels and structured errors.

Keep full M2 source, UTC calculation time, original unit/quantity declarations,
library versions, frame matrix/tolerance, indices, assumptions and references.
No unit conversion is inferred from vector length, no acceleration/gravity
combination occurs, and no source extrema, filtering or GPS timeline is calculated.
All five originals remain unqualified. A direct inspection of their longitudinal,
lateral and vertical vectors in that candidate order fails this numerical admission
policy for every file; that hypothesis is not a claimed exporter mapping and is
never silently repaired. Their six original vectors remain independently retained.

## Dependency and validation boundary

Adopt SciPy 1.18.1 exactly in the analysis extra, using the prior
[isolated audit](0004-analysis-contracts-and-library-policy.md) and current Windows
cp314 wheel/integration checks. Existing locked NumPy remains unchanged; GeographicLib
is deferred. PyPI listed no vulnerabilities for this version on the check date;
this is metadata evidence, not a full vulnerability audit. Actual installed SciPy
license notices include BSD and bundled OpenBLAS/LAPACK/GCC material and must be
retained for future redistribution.

Analytic tests use absolute/relative tolerances `1e-14`, separate from frame
admission and any future empirical app-comparison tolerance. Identity, signed
quarter-turns, a non-axis-aligned basis, inverted poses, inverse/norm invariants,
reflection/skew rejection, missingness, overflow, source binding and all five
fail-closed originals are checked. Exact Windows commands/results and remaining
limits belong in [M3 validation](../validation/M3.md).
M3 scientific acceptance, ADR 0003 owner review and source-app equivalence remain open.

Subsequent owner evidence: Manta screenshots and a source-bound directional
reconstruction are recorded in [ADR 0006](0006-app-reference-projection.md). This does
not change this ADR's strict exact-rotation admission or scientific API gates.
