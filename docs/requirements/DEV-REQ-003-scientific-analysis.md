# DEV-REQ-003 — Scientific Motion and GPS Analysis Engine

<!-- cspell:words AHRS stationarity Butterworth Goldens orthonormality acausal Missingness sosfiltfilt basemaps -->

**Milestone:** M3
**Status:** Proposed, documentation only
**Platform:** Windows / Python 3.14.6
**Precondition:** Verified M2 canonical importer contracts
**Owner decision:** No scientific computation is authorized by this document alone.

## 1. Purpose and scope

Build an offline, deterministic, provenance-aware scientific analysis engine for
Ride Forces recordings. Consume the immutable canonical M2 model; never rewrite
or alter original `.forces` files. Produce explicitly labeled acceleration,
rider-frame force, filtering, statistics and GPS products for later M4–M7 use.

The engine must distinguish measured or exported quantities, mathematically
derived values, assumptions, unknown units and calibrated results. A successful
numerical operation is not proof that its physical interpretation is correct.

In scope: coordinate-frame policies, acceleration magnitude, orientation and
vector projection under validated assumptions, filtering, numerical statistics,
quality flags, GPS geodesics, time alignment policies, reproducibility, comparison
against original app values, and tested library integration.

Out of scope: reimplementing sensor acquisition, inventing gyroscope samples,
certifying safety-critical accelerations, background tracking, live iPhone capture,
mapping a known track, UI, playback, rendering, exporting final video, and direct
changes to M2 source files.

## 2. Mandatory library architecture

- **LIB-001 NumPy:** Required core for finite vector arrays, projections,
  norms, matrix operations and reproducible numerical tests. Already specified
  under the optional `analysis` extra.
- **LIB-002 SciPy:** Required for `scipy.spatial.transform.Rotation`,
  `scipy.signal` filtering and `scipy.interpolate` methods. Use vetted
  library primitives rather than implementing signal-processing formulas anew.
- **LIB-003 Pint:** Required for unit-aware public boundaries and conversions
  once source-unit assignments have evidence. Keep inner numeric arrays in
  explicitly declared canonical SI or dimensionless units for performance;
  avoid allocating Pint objects for each individual sensor sample.
- **LIB-004 GeographicLib:** Required for WGS84 inverse geodesics, azimuths
  and inter-fix horizontal distances. Do not substitute planar Euclidean distance.
- **LIB-005 Pandas:** Optional adapter for tabular analysis and later consumers;
  avoid requiring it in every core numerical operation. Already in `analysis`.
- **LIB-006 AHRS:** Evaluation only, not a mandatory dependency. No complete
  gyroscope or magnetometer raw sequences were identified in the four baseline
  exports; prohibit claims of reliable full IMU sensor fusion from these files.
- **LIB-007 pyproj:** Optional extension only if a concrete coordinate reference
  system conversion need is approved. Do not duplicate GeographicLib's geodesic
  function for the initial feature set.
- **LIB-008 Dependency governance:** Verify license, locked version, Python
  3.14.6 and Windows wheel/build compatibility, security advisories, tests and
  compatibility before adding SciPy, Pint and GeographicLib via uv. Keep version
  choices reviewed and consistent with existing `pyproject.toml` and `uv.lock`.
  An upstream public API must not leak through the engine's stable domain API.

Reference APIs: SciPy Rotation and signal SOS, Pint, GeographicLib WGS84.
Official documentation URLs are provided in section 11.

## 3. Scientific contracts and coordinate semantics

- **SCI-001 Input:** Accept only typed, validated recordings returned by M2,
  including the source hash, schema version, sample rate, optional vectors and
  GPS fixes. Fail closed for unsupported inputs; no reinterpretation of raw JSON
  bypassing M2.
- **SCI-002 Provenance:** Every analysis product stores source SHA-256, analysis
  engine version, algorithm identifier, configuration, assumed unit system,
  coordinate convention, time basis, quality decisions and calculation timestamp.
- **SCI-003 Frames:** Define independent DEVICE, WORLD/GRAVITY and RIDER frames,
  their axis basis, right/left handedness, positive direction and unit.
  A frame transformation is permitted only when its interpretation is documented
  and approved in an ADR with reference tests.
- **SCI-004 Force terminology:** Distinguish accelerometer *specific force*
  (proper acceleration) from gravity vector and gravity-compensated kinematic
  acceleration. Avoid conflating accelerometer-derived rider loading with
  gravitational acceleration or automatically adding the gravity sequence.
  The original app's `accelerationSequence` relationship to
  `gravitySequence` must be empirically established.
- **SCI-005 Gravity convention:** Define standard gravity
  `g0 = 9.80665 m/s^2` separately from a measured gravity vector. Unit `g`
  as a loading factor is dimensionless when normalized by `g0`.
  A stationary instrument can indicate approximately 1 g of specific force,
  but sensor export conventions must be verified before imposing that on files.
- **SCI-006 Derived magnitude:** Permit mathematically clear
  `sqrt(x*x + y*y + z*z)` only with declared component units. Identify this
  as a **device-vector magnitude**, not automatically vertical rider G.
- **SCI-007 Rider projections:** Project via a verified orthonormal frame
  and documented matrix convention. Check dot products, vector norms,
  handedness, transformation direction, and whether vectors describe device
  axes, rider axes or calibration corrections. Record positive and negative
  vertical, lateral and longitudinal sign conventions explicitly.
- **SCI-008 Calibration:** Preserve original calibration and direction vectors;
  never silently normalize malformed/degenerate vectors or substitute defaults.
  Distinguish ORIGINAL_APP_REFERENCE, VALIDATED_RIDER_FRAME, DEVICE_ONLY and
  NOT_AVAILABLE capabilities. Report lack of rider-axis certainty.
- **SCI-009 Rotation:** Use SciPy Rotation when quaternion/matrix rotation is
  justified. Never synthesize quaternion orientation from gravity alone: yaw
  about gravity remains indeterminate without another reference.
- **SCI-010 Units:** No default GPS `speed` or `altitude` unit assignment
  without upstream evidence. GeographicLib returns distances in meters;
  GPS coordinate inputs are degrees under an explicitly stated WGS84 policy.
- **SCI-011 Missingness:** Invalid or unavailable data stay missing with quality
  flags; never replace with zero or interpolate across arbitrary gaps by default.
- **SCI-012 Source independence:** Never overwrite M2 objects, timestamps,
  calibration vectors, extrema or the original source.

## 4. Time-series and filtering

- **SIG-001 Time basis:** Derived `sample_index / sample_rate` is labeled
  INFERRED_UNIFORM, not the raw device timestamp. Source GPS timestamps and
  numeric `date` epochs remain unverified until an ADR documents evidence.
- **SIG-002 Preserve raw:** Retain unfiltered samples and report both raw and
  filtered results separately. A filtered peak may not be presented as a raw peak.
- **SIG-003 Filter engine:** Support no filter and a configurable Butterworth
  SOS zero-phase offline filter through `scipy.signal.sosfiltfilt`; make cutoff,
  order, passband, sampling frequency and edge handling explicit.
- **SIG-004 Zero-phase qualification:** A forward/backward filter eliminates
  phase lag within its algorithmic assumptions but is acausal and unsuitable as
  a live causal measurement. It can alter peak amplitude and has edge artifacts.
  Short segments that do not satisfy pad requirements must return diagnostics,
  not silently switch methods.
- **SIG-005 Additional filters:** Optional simple moving-average and median
  filters only as separately identified algorithms, each with exact window,
  boundary and missing-data behavior; not implicit defaults.
- **SIG-006 Events:** Reproducible peaks, troughs, threshold duration and
  per-axis extrema must use explicit inclusive/exclusive segment boundaries
  and raw/filtered selection. No hard-coded thresholds for ride safety.
- **SIG-007 Interpolation:** Future-frame sampling needs an explicit,
  policy-driven interpolation function on a validated monotonic time axis;
  no extrapolation by default. Keep this mathematical primitive independent
  of M5 playback.
- **SIG-008 No artificial precision:** Retain provenance of 50 Hz samples,
  observed rate limitations and inferred time. Interpolation must not be
  presented as additional physical sensor measurements.
- **SIG-009 Statistics:** Include sample count, minimum, maximum, mean,
  root-mean-square and selected quantiles for each qualified channel.
  Definitions for time-weighted statistics and sample intervals must be stated.
- **SIG-010 Quality:** Track missing/invalid inputs, too-short segments,
  optional marker uncertainty, filter edge sensitivity, outliers and potential
  sensor clipping as *indicators*, not confirmed sensor faults.

## 5. GPS and geodesic contracts

- **GPS-001 Data quality:** Keep each fix with original coordinates,
  timestamps and accuracy metadata, including negative reported speed,
  course and accuracy values. Treat apparent sentinels as unavailable
  **for optional derived computations only** with explicit diagnostics,
  without replacing the original values or asserting undocumented semantics.
- **GPS-002 Validation:** Latitude [-90,90], longitude [-180,180] and finite
  numeric values are required for computed WGS84 segments. Invalid points are
  excluded from derived segments with a reason; original records remain intact.
- **GPS-003 Geodesics:** Use `Geodesic.WGS84.Inverse` for horizontal inter-fix
  distances and forward azimuth. Report horizontal ellipsoidal distance,
  not 3D track length or ride manufacturer's track specification.
- **GPS-004 Quality gating:** Configurable policy uses horizontal accuracy,
  time monotonicity, duplicate timestamps, speed/accuracy flags and implausible
  jumps. Define strict and exploratory profiles; log excluded segments and
  avoid false precision. No arbitrary silent thresholds.
- **GPS-005 Distance:** Summed accepted segments are a **GPS-derived horizontal
  path estimate** only. Also report coverage, segment counts and uncertainty
  limitations. Do not bridge invalid gaps by default.
- **GPS-006 Derived speed:** Use distance/time only with a validated time
  basis and positive time differences. Label estimated speed separately from
  reported GPS speed and preserve the original speed field and its unknown unit.
- **GPS-007 Altitude:** Altitude sequence may be displayed raw, but do not
  claim validated heights or cumulative elevation without documented altitude
  datum, accuracy and quality policy.
- **GPS-008 Sensor alignment:** No exact GPS-to-motion timeline mapping unless
  the source date epoch and GPS timestamp offset are verified. Preserve separate
  time bases; any candidate alignment must be labeled provisional and testable.
- **GPS-009 No map service:** Offline numerical processing only; geocoding,
  reverse lookups, basemaps and uploads are outside M3.
- **GPS-010 No track reconstruction claim:** Curved rail path, inversions and
  magnetic/structural GPS obstructions make GNSS paths poor physical rail
  reconstructions; do not equate result with track geometry or speed certification.

## 6. Results and quality models

- **RES-001:** Export a typed, immutable `AnalysisResult` with channels,
  quantity labels, units, frame labels, sample-time description, raw/filtered
  flags, result validity, diagnostics and reproducibility metadata.
- **RES-002:** Each computed channel has capability state VERIFIED,
  PROVISIONAL, UNAVAILABLE or INVALID; no provisional coordinate math hidden
  behind a definitive `vertical_g` property.
- **RES-003:** Define `AnalysisProfile` with deterministic default
  `raw_device_only` and independently approved `rider_calibrated`,
  `gps_exploratory` and `gps_strict` settings.
- **RES-004:** Ensure output suitable for M4 charts, M5 timeline and M6
  rendering, without importing Qt, FFmpeg or storage infrastructure.
- **RES-005:** A documented algorithm/schema migration policy must permit
  analysis recomputation from original M2 data. Results are derived artifacts,
  not edits to original recordings.

## 7. Validation and scientific acceptance

- **VAL-001:** Create synthetic golden references: constant 1 g stationarity
  under an explicitly defined simulated sensor convention, free-fall-like
  zero-specific-force vector, orthogonal and inverted rider axes, known
  rotations, known peaks, missing samples and distorted vectors.
- **VAL-002:** Verify NumPy norms/matrix projections and SciPy rotations against
  analytically calculated vectors; run orthogonality and sign tests, including
  handedness and transpose-direction defects.
- **VAL-003:** Verify filtering with constant, step, sine, impulse and short
  sequences. Measure filter-induced peak changes and edge effects; test
  exact profile parameter retention.
- **VAL-004:** Verify Pint unit conversions and dimensional correctness at
  API boundaries. Reject unknown source-unit assignments rather than guessing.
- **VAL-005:** Verify GeographicLib against documented geodesic examples,
  identical points, known WGS84 baselines, missing fixes and invalid coordinate
  cases. Prohibit comparing horizontal distance to a 3D rail track directly.
- **VAL-006:** Parameterize structural integration tests for all four actual
  fixtures without modifying their bytes; test absent ride position, variable
  metadata and GPS availability separately.
- **VAL-007:** Compare `minForce` and `maxForce` from originals with the
  source Ride Forces app's displayed metrics after confirming the app's
  chosen axis, smoothing, recording segment and sign conventions. If no
  independently captured reference exists, mark equivalence **UNVERIFIED**,
  publish a discrepancy report and do not assert a match.
- **VAL-008:** Record numeric tolerances for synthetic calculations separately
  from empirical app-comparison tolerances. No arbitrary acceptable deviation
  for unknown source algorithms.
- **VAL-009:** All required Windows quality checks from `AGENTS.md`
  pass, including dependency tests, and both pull-request CI jobs pass before
  marking milestone complete. Evidence recorded in `docs/validation/M3.md`.
- **VAL-010:** Benchmark representative batch/array execution with explicit
  environment, recordings, timing and memory. No unsupported real-time claim.

## 8. Acceptance criteria

- **AC-01:** Documented, reviewed scientific ADR for source units, gravity,
  frames, sign, time and unknowns; no unsupported default rider-frame output.
- **AC-02:** Version-pinned NumPy, SciPy, Pint and GeographicLib dependency
  decisions with Windows/Python compatibility, license and CI evidence.
- **AC-03:** Deterministic immutable raw and calculated channel API with full
  provenance and capability flags.
- **AC-04:** Analytic norms, projections and rotations verified by synthetic
  golden cases, including negative and inverted axes.
- **AC-05:** Explicit raw-versus-filtered computations validated and edge cases
  diagnosed; filter parameters recorded and peaks not silently overwritten.
- **AC-06:** Unit normalization validated with Pint; unverified source units
  remain unassigned.
- **AC-07:** GPS geodesics, speed estimates and quality filtering validated
  with synthetic cases and all four fixtures without inventing GPS precision.
- **AC-08:** App comparison report includes source `minForce`/`maxForce`,
  same-segment analysis and explicit unresolved assumptions; claims of
  equivalence require evidence beyond recorded extrema alone.
- **AC-09:** No source recording mutation, no mandatory network calls,
  no Qt coupling, no feature creep into M4–M7.
- **AC-10:** Focused scientific tests, complete native-Windows checks and
  both actual GitHub PR CI jobs pass; M3 validation report records results.

## 9. Evidence gates and unresolved questions

Document evidence separately for all four recordings as defined in
[the M2 format analysis](FORMAT-ANALYSIS.md). The available files establish
sample arrays, GPS entries, direction vectors, sample rate and source
extrema, but **not** definitive axis semantics, sensor unit meanings,
time epoch or upstream smoothing formula.

A scientific implementation must not proceed to a definitive rider-force
calculation without resolving those issues from documented source-app
behavior or measured reference tests. Device-only analyses may be delivered
while rider-frame features remain unavailable or provisional. Missing evidence
must produce a recorded limitation, not a fabricated calibration.

Questions for an ADR or a reference-data collection protocol:

- Does `accelerationSequence` represent device proper acceleration in g,
  gravity-compensated acceleration, or another transformed source quantity?
- Is `gravitySequence` dimensionless in g or measured in a different unit?
- How are direction/calibration vectors defined relative to the iPhone and rider?
- What axis, segment and filter produce Ride Forces `minForce` and `maxForce`?
- Are numeric `date` and GPS timestamps Apple-reference-date seconds?
  Do **not** implement this assumption without verification.
- What units and invalid-value sentinels do source GPS speed and altitude use?
- Is `endIndex` inclusive for derived statistics?

## 10. Implementation and change control

Follow [PLAN.md](../implementation/DEV-REQ-003/PLAN.md) and
[PROMPTS.md](../implementation/DEV-REQ-003/PROMPTS.md) in order.
Do not implement M3 until M2 contract readiness is confirmed and a separate
implementation instruction is given. Do not alter this accepted requirement
silently; any substantive changes require a reviewed requirement revision.

## 11. Primary documentation

- [SciPy Rotation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.html)
- [SciPy SOS filtering](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html)
- [NumPy documentation](https://numpy.org/doc/stable/)
- [Pint documentation](https://pint.readthedocs.io/en/stable/)
- [GeographicLib Python](https://geographiclib.sourceforge.io/html/python/)
- [AHRS documentation](https://ahrs.readthedocs.io/)
