# ADR 0003 — Scientific semantics and capability gates

<!-- cspell:words orthonormality -->

Status: Deferred general-scientific proposal; not a reduced-M3 completion gate.
The current [requirements](../requirements/DEV-REQ-003-scientific-analysis.md) use
the adopted [ADR 0006](0006-app-reference-projection.md) app-reference policy,
existing centered mean and planned basic extrema. This research proposal retains
scientific distinctions and reference protocols without authorizing computation,
GPS analytics or universal physical calibration. Existing generic APIs still
require their explicit unit/frame evidence. The current
[plan](../implementation/DEV-REQ-003/PLAN.md) defines remaining product work.

## Context and verified boundary

Reviewed at repository revision `0db96029c724edccb8175c7843bf8f18be3b808d`:
[public service](../../src/ride_forces_analyzer/importers/service.py),
[result types](../../src/ride_forces_analyzer/importers/result.py),
[canonical models](../../src/ride_forces_analyzer/domain/models.py),
[source ownership](../../src/ride_forces_analyzer/domain/source.py),
[motion](../../src/ride_forces_analyzer/importers/motion.py) and
[optional validation](../../src/ride_forces_analyzer/importers/optional.py).
Existing tests reconfirmed these contracts on native Windows Python 3.14.6/uv;
exact commands/outcomes are recorded in the plan.

`import_forces(Path, *, limits=DEFAULT_LIMITS)` and
`import_forces_bytes(bytes, *, limits=DEFAULT_LIMITS)` return immutable
ImportSuccess/ImportFailure. Only full success supplies a Recording for future
analysis; decode/motion/optional subset success alone is insufficient. SourceEnvelope
owns exact original bytes, SHA-256 and an immutable tree. SourceNumber retains exact
JSON number tokens; motion strings remain strings in that tree. Finite float
accessors establish neither physical units nor interpretation. Failure has no Recording.

MotionSequence preserves acceleration and optional equal-length gravity tuples.
`paired_motion_available` establishes structural pairing, not proven simultaneous
capture, common physical units or gravity compensation. RecordingVectors are six
optional structural vectors, not a validated rotation. GPS has independent indexed
slots, ABSENT/PRESENT/INVALID status and optional members; `fix=None` retains an
unusable slot. Date, smoothing factor and extrema remain source numbers.

Defaults are owner policy: effective rate 50 and riding position Seated apply only
to absence, with DEFAULT origin; source fields remain absent. A present valid value
has SOURCE origin. Neither default proves measured timing or sensor mounting.
No M2 code adds gravity, projects rider axes, converts dates, filters or aligns GPS.

## Recording evidence

All five complete originals match the [pinned byte lengths and SHA-256 catalog](../development/RECORDINGS.md)
and [recursive inventory](../../tests/fixtures/schema-inventory.json).
The following counts were also reconfirmed through both public adapters.

| Fixture       | Device      | Acceleration | Gravity | GPS    | Effective rate / origin | Riding position / origin |
| ------------- | ----------- | ------------ | ------- | ------ | ----------------------- | ------------------------ |
| Iron Gwazi    | Apple Watch | 8712         | absent  | absent | 50 / SOURCE             | Seated / SOURCE          |
| Kraken        | iPhone      | 10084        | 10084   | 174    | 50 / SOURCE             | Seated / SOURCE          |
| Manta         | iPhone      | 9640         | 9640    | 193    | 50 / SOURCE             | Flying / SOURCE          |
| Taron         | iPhone      | 9089         | 9089    | 182    | 50 / DEFAULT            | Seated / DEFAULT         |
| VoltronNevera | iPhone      | 10504        | 10504   | 149    | 50 / DEFAULT            | Seated / DEFAULT         |

Every current motion component is a numeric string; there are no motion-sample
timestamps, raw gyroscope/magnetometer sequences or per-sample attitude quaternions.
Device identifies expected availability, not acquisition API or axis convention.
The four iPhone files cannot establish a universal Watch policy, or vice versa.
Iron Gwazi's gravityIndex=7382 is retained despite absent gravity; it cannot supply
a gravity sample. Taron's gravityIndex=1513 precedes startIndex=2284 and must remain
independently bounded, not reordered or removed. endIndex inclusion remains unknown.

All 698 GPS fixes have finite source numbers. Their adjacent timestamps increase
within each current file; numeric ordering alone establishes no epoch, duration unit,
offset, capture simultaneity or clock accuracy. GPS and motion counts differ.
All negative speed/course/accuracy values in these originals are -1. Per-file
GPS_NEGATIVE_VALUE counts are Kraken 92, Manta 144, Taron 92 and VoltronNevera 134;
Iron Gwazi has no GPS and no such diagnostics. Field-level counts are in
[FORMAT-ANALYSIS.md](../requirements/FORMAT-ANALYSIS.md). No negative horizontal or
vertical accuracy occurs in this corpus; later inputs still require the same policy.

Exact source extrema are observations, with unknown axis, unit and processing:

| Fixture       | minForce source token | maxForce source token |
| ------------- | --------------------- | --------------------- |
| Iron Gwazi    | -1.3335281610488892   | 3.784377098083496     |
| Kraken        | -0.22021731734275818  | 4.076864719390869     |
| Manta         | -3.720832109451294    | 2.6144702434539795    |
| Taron         | -0.6263444423675537   | 4.345596790313721     |
| VoltronNevera | -1.5981999635696411   | 4.365312576293945     |

Every smoothingFactor token is `1`. This does not prove an unfiltered sequence,
window size, filter family or source-extrema formula. Manta's negative extreme
and Flying metadata do not establish a sign inversion or permit a Seated transform.
No extrema have been recomputed or compared against an independently captured UI.

## Primary references and their limits

The developer's [recording types](https://rideforces.com/guides/recording-types/)
describe standard accelerometer recordings and advanced sensor/orientation/GPS data.
[Accuracy guidance](https://rideforces.com/guides/improving-accuracy/) asks users to
keep the device stable, with additional wrist/arm guidance for Watch recordings.
[Editing guidance](https://rideforces.com/guides/editing/) states that graph selection
affects statistics and that smoothing/calibration can be adjusted.
[Force guidance](https://rideforces.com/guides/understanding-forces/) distinguishes
combined from directional results without giving an export formula or axis signs.
These are current public app descriptions, not a version-matched 2.2.0 export
specification, source code review or per-fixture UI reference.

Apple documents [CMAcceleration](https://developer.apple.com/documentation/coremotion/cmacceleration)
in g units and [userAcceleration](https://developer.apple.com/documentation/coremotion/cmdevicemotion/useracceleration)
separately from [gravity](https://developer.apple.com/documentation/coremotion/cmdevicemotion/gravity),
which is expressed in the device reference frame. Its API describes total sensor
acceleration as gravity plus userAcceleration. This identity applies to that API;
it does not identify which quantity, sign or transform Ride Forces stores.

Core Location documents [speed](https://developer.apple.com/documentation/corelocation/cllocation/speed)
in meters per second with negative values invalid, and
[course](https://developer.apple.com/documentation/corelocation/cllocation/course)
in degrees clockwise from north with negative values invalid.
[Horizontal accuracy](https://developer.apple.com/documentation/corelocation/cllocation/horizontalaccuracy)
is a meter-based uncertainty whose negative value invalidates the coordinate.
These field-specific meanings are hypotheses for similarly named export fields,
not verified exporter contracts. A negative altitude is not an invalidity rule.
Apple's [reference-date initializer](https://developer.apple.com/documentation/foundation/nsdate/init(timeintervalsincereferencedate:))
uses seconds relative to 2001-01-01 UTC; other Date encodings exist. A numeric JSON
date/timestamp and plausible calendar conversion do not identify the chosen encoding.
Primary documentation was checked through web lookup and Context7; no private
Ride Forces algorithm or app runtime was inspected.

## Proposed decisions and unresolved evidence matrix

The decisions below constrain future work; they are not implemented analysis.

| Topic                   | Known fact / candidate                                   | Safe proposed policy                                             | Evidence needed to qualify physical output                                |
| ----------------------- | -------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Acceleration quantity   | Finite vectors; app describes accelerometer acquisition  | Keep exported device scalars; quantity/unit UNKNOWN              | Versioned exporter mapping and controlled signed reference captures       |
| Gravity                 | iPhone paired arrays; Watch gravity absent               | Keep source gravity separate; never add/subtract by field name   | Quantity, sign, unit, frame and pairing reference for each source profile |
| Units                   | Apple APIs use documented units; export mapping unknown  | No g/SI or GPS unit assignment from names or magnitude           | Verified adapter binding plus unit-conversion reference tests             |
| Direction / calibration | Six structural vectors and marker indices                | No normalization, frame completion or rider projection fallback  | Axis/mount/pose definitions and independent calibration references        |
| Yaw                     | A gravity direction supplies no heading reference        | No full orientation/quaternion from gravity alone                | Independent heading or verified non-collinear frame reference             |
| Source extrema          | Exact minForce/maxForce and smoothingFactor tokens       | Separate source values from any future derived statistics        | Same app version, segment, axis, sign and smoothing comparison            |
| Epoch / alignment       | Source date/timezone and separate numeric GPS timestamps | Preserve; inferred rate timeline only, no absolute conversion    | Exporter encoding, seconds scale, origin and measured motion/GPS offset   |
| Negative GPS values     | Current flagged values are -1                            | Exclude affected optional derived use; retain all raw evidence   | Field-specific export validity rules and approved quality profile         |
| Unknowns                | Import success supplies data, not semantic certainty     | Raw inspection remains usable; restricted channels stay explicit | Owner review accepts the documented scope, never converts guesses to fact |

### Measurement nomenclature and units

Use three distinct concepts: specific force (proper acceleration; non-gravitational
force per unit mass), gravitational acceleration, and kinematic acceleration.
In an explicitly declared inertial convention expressed in a common basis,
`f = a - g`; a supported stationary instrument has nonzero specific force and an
ideal freely falling instrument has zero specific force. These are definitions
and future synthetic references, not classifications of current exported samples.
Apple's signed sensor decomposition must not be substituted into this physical
equation without a verified mapping. A Watch wrist measurement is device-local;
it is not automatically rider center-of-mass or seat loading.

The project normalization constant is `g0 = 9.80665 m/s^2` per SCI-005.
`f/g0` is a dimensionless load ratio, distinct from measured/estimated gravity.
No source field acquires that normalization implicitly, and acceleration-derived
loading is not a force in newtons without an independently specified mass/model.
A future device-vector magnitude requires a declared common component unit;
with unknown units only raw source scalars are eligible for the default view.
Do not use gravity magnitude as an automatic sensor-scale correction or fill
missing Watch gravity with zero, 1 g or a vector inferred from acceleration.

### Frame convention and yaw

Propose right-handed, orthonormal frames with column-vector coordinates:

- DEVICE preserves source `(x, y, z)` ordering. Its physical directions and
  signs are UNKNOWN until the per-device exporter/mount mapping is verified.
- WORLD/GRAVITY uses an evidence-qualified upward Z direction. Gravity alone
  leaves rotation about that direction unresolved; X/Y cannot be labeled north/east,
  rider-forward or a complete attitude without an independent reference.
- RIDER proposes X longitudinal-forward, Y lateral-left and Z rider-up.
  This is a project convention, not a claim about Ride Forces. The precise
  rider/seat pose and mounting definition require owner review and reference
  captures, especially Manta's Flying pose; Seated metadata does not settle them.

For qualified frames, passive component conversion is `v_R = R_R_from_D v_D`;
the rows are the RIDER unit basis expressed in DEVICE coordinates. Require
orthonormality, determinant +1 and inverse `R_D_from_R = transpose(R_R_from_D)`.
Future tests must detect sign, reflection and transpose errors, including inverted
reference poses. Tolerances and actual exported-vector eligibility are deferred
to validated numerical/frame stages; none are invented here. Mathematically valid
vectors or rotations alone do not establish a physical mapping. A partial tilt
estimate, if later justified, must not be promoted to full attitude. GPS travel
course does not automatically resolve device/rider yaw or body motion.

### Time, GPS and sentinel gates

A later relative `sample_index / effective_rate` coordinate must be named
INFERRED_UNIFORM, preserve SOURCE/DEFAULT rate origin and state its selected index
origin. There are no measured motion-sample times to prove uniform acquisition,
clock synchronization or absence of gaps. Until evidenced, neither `date` nor GPS
timestamps become Unix/Apple wall time; timezone text cannot resolve the epoch.
Even time differences need a verified seconds scale before deriving physical speed.

Treat negative reported speed/course or accuracy as unusable for the affected
optional derived product, with an explicit reason, while leaving the entire M2
fix, slot and original value intact. Do not universally classify negative numbers
as sentinels: altitude may be negative; source extrema may be signed. Negative
horizontal accuracy excludes a coordinate-based derived segment conservatively;
negative vertical accuracy excludes altitude-derived use. Negative speed/course
or their accuracies do not alone discard otherwise qualified horizontal coordinates.
Their exact exported meanings remain unknown. No sentinel replacement, silent
interpolation or gap bridging is allowed.

GPS horizontal geometry requires finite valid coordinate bounds and an explicit
reviewed WGS84/degrees assignment. A strict accuracy policy additionally needs
documented units and thresholds. Exploratory assumed WGS84 geometry must be
explicitly opt-in, PROVISIONAL and separate from qualified output. Time/speed and
motion-alignment gates are independent from coordinate geometry. GPS distance is
at most a horizontal path estimate, never certified 3D rail length or ride speed.
Iron Gwazi has no GPS/gravity-derived channels; its markers or other fixtures
cannot supply missing data.

## Capability gates and acceptance of unknowns

Proposed eligibility is per channel/profile/source, not per successful file import:

| Capability                 | Minimum evidence / gate                                    | Current fixture policy                                    |
| -------------------------- | ---------------------------------------------------------- | --------------------------------------------------------- |
| DEVICE_ONLY raw inspection | M2 full success; retained source identity/types            | All five eligible for raw scalars; units/axes UNKNOWN     |
| Device-vector magnitude    | Declared common component unit and tested math             | No physical magnitude yet; raw data only                  |
| Gravity-compensated motion | Verified quantity/unit/sign/frame and sample pairing       | Unavailable; Watch gravity absent, iPhone semantics open  |
| VALIDATED_RIDER_FRAME      | Approved frame/pose evidence and synthetic/empirical tests | Unavailable for every original                            |
| ORIGINAL_APP_REFERENCE     | Independently captured matching app settings/UI/export     | No current qualifying reference                           |
| GPS geometry               | Valid slots, reviewed coordinates/datum/quality policy     | iPhone data retained but qualification open; Watch absent |
| GPS physical speed / sync  | Qualified geometry/time scale; verified offsets for sync   | Unavailable; epochs/scale/alignment open                  |

NOT_AVAILABLE describes a capability exclusion. Proposed channel states remain
VERIFIED, PROVISIONAL, UNAVAILABLE and INVALID per RES-002. VERIFIED is scoped
to its stated quantity, unit, frame and evidence; M2 structural verification must
never be relabeled as verified rider loading. Missing inputs or unresolved physical
semantics yield UNAVAILABLE; supplied data that fail a defined computation-specific
contract yield INVALID. Keep the reasons distinct. PROVISIONAL requires an explicit
opt-in profile, named assumptions and separated results; it never satisfies a
definitive rider-force or app-equivalence acceptance gate.

Each future artifact must retain source SHA-256, engine/algorithm version,
configuration, unit/frame/time assignments, raw/filtered status and channel evidence.
Its calculation timestamp is separate from unconverted source dates. Changing
policy requires recomputation from retained M2 data, never rewriting an original.

The future `raw_device_only` default exposes retained source scalars and provenance,
not g-labeled rider channels. It must not silently enable rider_calibrated or GPS
profiles. Unknowns are valid documented outcomes, not zeros or errors hidden by
fallback. Owner approval can accept exclusions for milestone scope; it cannot
establish units, calibration, epoch or app equivalence without evidence.
AC-01 still needs owner ADR review; AC-08 requires the later comparison record.
Neither is fully accepted by this Stage 0 draft, and M3 remains open.

## Reference collection and next-stage gate

For each device/acquisition profile and app version, retain a source-hash-linked
record of sensor/mount orientation, Watch wrist/arm stability, ride pose, raw API
mapping if available, calibration settings/markers, graph interval and smoothing.
Collect controlled stationary and signed-orientation references separately from
ride statistics. Free-fall-like references belong to synthetic tests; no risky
recording experiment is required. New real recordings still need separate owner
authorization. Obtain external heading/frame evidence where rider axes require it.

Capture source-app screens/values for each original with the exact segment, force
channel and smoothing settings; record unavailable settings explicitly. Determine
endIndex inclusion from a controlled boundary case, not a fitted extrema match.
Check exported dates/GPS times against a known clock and encoding, and separately
measure any motion/GPS offset. Compare quantities only after unit/frame/time gates
match. Keep synthetic numeric tolerances separate from empirical discrepancy
criteria; no percentage tolerance for an unknown algorithm is proposed.

Stage 1 may design APIs/dependency policy only after a separate owner instruction;
this ADR identifies unresolved evidence without installing libraries or performing
scientific calculations. Before any definitive rider interpretation, review the ADR
and supply qualifying references or retain the exclusion. Source bytes, all GPS
data and M2 contracts remain unchanged. No next stage starts automatically.
