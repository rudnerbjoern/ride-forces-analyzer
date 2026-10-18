# Analysis contracts and device primitives — DEV-REQ-003

The [analysis package](../../src/ride_forces_analyzer/analysis/) exposes executable
model contracts. `analysis.device` provides opt-in qualified DEVICE vectors/norms
and Pint conversion; explicit provisional frames and source-app calibrated
projection are implemented as separate contracts below.
Use the already locked NumPy from the `analysis` extra. The regular bootstrap
and M2 importer do not import this package. The
[library/API ADR](../decisions/0004-analysis-contracts-and-library-policy.md)
records audit evidence, adoption gates and API migration policy;
[ADR 0003](../decisions/0003-scientific-semantics-and-capability-gates.md) remains
the proposed scientific qualification policy.

## Public model shape

| Model / label      | Contract                                                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| AnalysisProfile    | Profile name/schema, frozen scalar configuration, policy/assumption references, explicit provisional permission           |
| AnalysisResult     | Full M2 ImportSuccess, profile, provenance, tuple channels, ordered diagnostics, result schema                            |
| AnalysisChannel    | Identifier, quantity/unit/frame, capability, source sequence/indices, time basis, processing, samples or exclusion reason |
| SampleValues       | Owned float64 byte snapshot, immutable shape/row-validity, fresh read-only NumPy view                                     |
| UnitAssignment     | Canonical unit label, UNKNOWN/ASSUMED/VERIFIED state and references                                                       |
| TimeBasis          | Index/inferred/unverified/verified-seconds label, optional M2 rate/origin, epoch only when verified                       |
| AnalysisProvenance | Retained M2 provenance, engine/algorithm identity, explicit UTC calculation time                                          |
| AnalysisDiagnostic | Stable code, reused M2 severity, message, optional channel and source index                                               |

Every constructor performs runtime validation. Model collections own tuples or
read-only scalar mappings. Supply tuple collections to the typed public API;
runtime ownership also protects against mutable collections passed around typing.
Schema version `1` is the initial contract identifier, not a serialization format.
Any later persistence/serialization adapter must document compatible schema and
algorithm changes rather than treating every version string as interoperable.

## Raw values and qualified quantities

`AnalysisProfile()` is raw_device_only, with no processing configuration or
assumptions. It permits SOURCE_VALUES/RAW channels with UNKNOWN units. A VERIFIED
raw channel says its data contract is established; it does not certify physical
axes, source acquisition semantics or rider G. Keep canonical originals through
`result.source.recording.source`; import warnings remain in `result.source.diagnostics`.

SPECIFIC_FORCE, GRAVITY, KINEMATIC_ACCELERATION and DEVICE_VECTOR_MAGNITUDE use
explicit canonical `m/s^2`; LOAD_FACTOR is dimensionless; DISTANCE/ALTITUDE,
SPEED and ANGLE require `m`, `m/s` and `deg`. Available physical values cannot
use UNKNOWN units. VERIFIED physical values require VERIFIED unit references;
ASSUMED assignments require a PROVISIONAL channel and a separately approved
opt-in profile with named assumptions. Reference strings are caller attestations,
not automatic qualification of a source. No current real fixture is assigned these
units or projected into RIDER/WORLD_GRAVITY by the implemented models.

Interpreted frames require references. The proposed right-handed/passive convention
and unresolved yaw/pose mapping remain in ADR 0003. Ordinary DEVICE labels retain
source x/y/z, not known Earth or rider directions. Pint's `g` symbol is gram,
not the project's dimensionless loading ratio; future conversion must use the
explicit standard-gravity normalization policy, never an ambiguous symbol.

Unavailable/invalid channels have `samples=None`, no source indices and a reason.
Within available arrays, missing rows require explicit NaN and `valid_rows=False`;
valid zero requires a finite sample and `True`. No hidden finite placeholder,
infinity or inferred missingness is accepted. Partial missing rows must stay
explicit in future algorithm diagnostics; this stage implements no recovery math.

Source indices and indexed diagnostics are bounded against their own acceleration,
gravity or GPS sequence, not a common length. Iron Gwazi's missing gravity/GPS
cannot be referenced by available channels. This validation neither aligns clocks
nor normalizes/changes M2 marker indices.

## Immutability and determinism

SampleValues copies numeric input into little-endian float64 bytes. It does not
retain a writable ndarray alias. `samples.values` is a fresh ndarray view over
immutable bytes: its WRITEABLE flag cannot be enabled. Caller view metadata cannot
change the model's shape, dtype or next accessor. `values.copy()` is a mutable,
independent work array. Source precision/types remain in the immutable M2 envelope;
the float64 snapshot is an explicit canonical numerical representation.

Diagnostics sort ERROR, WARNING, INFO, then channel ID, source index (rows without an index
first) and code. Exact-key ties preserve supplied order. Messages should describe
defects without raw GPS/source payloads. Result validity is INVALID for error
diagnostics/invalid channels, RESTRICTED for provisional/unavailable channels,
otherwise VALID. That describes the supplied result contract, not blanket
scientific accuracy. Timestamp generation is absent;
callers must supply the UTC calculation time explicitly for reproducible results.

## Model-only construction example

This example copies a typed M2 component; it performs no physical calculation:

```python
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ride_forces_analyzer.analysis import (
    AnalysisChannel,
    AnalysisProfile,
    AnalysisProvenance,
    AnalysisResult,
    CapabilityState,
    FrameLabel,
    QuantityKind,
    SampleValues,
    SourceSequence,
)
from ride_forces_analyzer.importers import ImportSuccess, import_forces

source = import_forces(Path("example.forces"))
if isinstance(source, ImportSuccess):
    copied_x = np.array([v.x for v in source.recording.motion.acceleration], dtype=np.float64)
    channel = AnalysisChannel(
        "source-x",
        QuantityKind.SOURCE_VALUES,
        CapabilityState.VERIFIED,
        SourceSequence.ACCELERATION,
        frame=FrameLabel.DEVICE,
        samples=SampleValues(copied_x),
        source_indices=tuple(range(len(copied_x))),
        columns=("x",),
    )
    result = AnalysisResult(
        source,
        AnalysisProfile(),
        AnalysisProvenance(
            source.recording.source.provenance,
            "example-model-caller",
            "source-component-copy",
            datetime(2026, 10, 14, tzinfo=UTC),
        ),
        (channel,),
    )
```

The example time identifies this illustrative caller operation, not the recording
epoch. Production callers choose their own explicit calculation time.

## Verification and scope

```powershell
uv run --locked pytest -o cache_dir=.tmp/pytest-cache tests/test_analysis_models.py
```

Tests cover caller aliases/read-only views, explicit missing versus zero,
configuration/tuple ownership, unit/frame/profile gates, provenance/time rejection,
deterministic diagnostic order, independent indices and all five read-only fixtures.
A fresh-process check denies file/network access during construction, verifies
no Qt import and requires no SciPy/Pint/GeographicLib import. Synthetic qualified
descriptors test structural gates, not the actual files' scientific semantics.

Source-app projection/centered mean is implemented separately in analysis.reference.
Reduced M3 includes selected-range extrema and focused acceptance; additional
filters, universal physical calibration and broad statistics are deferred, while
GPS analytics is outside current scope. No fixture
is reformatted and no new project dependency is adopted by this contract layer.

## Device-only vectors and units

Public opt-in API: `ride_forces_analyzer.analysis.device` (NumPy and Pint analysis
extra required). Importing just `analysis` models does not import Pint.

- `MotionUnitContract(source_sha256, source_sequence, unit, quantity, unit_evidence, quantity_evidence)`:
  immutable source-specific caller attestations. Unit and physical meaning require
  separate nonempty references; strings alone do not prove source-app semantics.
  Supported DeviceAccelerationUnit members: SI, CENTIMETERS, FEET, STANDARD_GRAVITY.
  QuantityKind must identify SPECIFIC_FORCE, GRAVITY or KINEMATIC_ACCELERATION.
- `convert_device_vectors(samples, contract) -> SampleValues`: common-unit x/y/z
  rows into SI, preserving owned bytes and explicit invalid rows. This primitive
  validates the contract and shape; its caller must enforce source binding.
- `device_vector_norm(channel) -> AnalysisChannel`: verified raw DEVICE SI x/y/z
  into a separately identified DEVICE_VECTOR_MAGNITUDE channel. Stable NumPy
  Euclidean norm; no frame transformation or source relationship.
- `analyze_device_vectors(source, *, calculation_time, acceleration_contract=None, gravity_contract=None) -> AnalysisResult`:
  full M2 input only, source/sequence binding enforced, separate vector and norm
  channels for each motion sequence. Caller supplies aware UTC calculation time.
  `device_vectors` profile records original units, meanings and library versions;
  channel evidence, source indices and complete M2 provenance are retained.

Absent data or undeclared units yield UNAVAILABLE products with no samples and
SOURCE_SEQUENCE_ABSENT / SOURCE_UNIT_UNKNOWN warnings. Hash/type/contract defects
raise ValueError/TypeError; finite-range defects yield INVALID products and
UNIT_CONVERSION_RANGE / DEVICE_NORM_RANGE errors. Usable vectors survive norm
overflow. Diagnostics retain deterministic model ordering. Source data/diagnostics,
GPS, unknown fields, numeric strings and extrema are untouched.

Example for an imported synthetic source whose independent test protocol explicitly
specifies common SI components and specific-force meaning:

```python
from datetime import UTC, datetime
from ride_forces_analyzer.analysis import QuantityKind, SourceSequence
from ride_forces_analyzer.analysis.device import (
    DeviceAccelerationUnit,
    MotionUnitContract,
    analyze_device_vectors,
)

# imported is full M2 ImportSuccess; these references must concern that exact source.
contract = MotionUnitContract(
    imported.source_sha256,
    SourceSequence.ACCELERATION,
    DeviceAccelerationUnit.SI,
    QuantityKind.SPECIFIC_FORCE,
    ("synthetic protocol: m/s^2 for every orthogonal device component",),
    ("synthetic protocol: specific force, independent of gravity export",),
)
result = analyze_device_vectors(
    imported,
    calculation_time=datetime(2026, 10, 14, tzinfo=UTC),
    acceleration_contract=contract,
)
```

Stationarity tests declare synthetic specific force +g0 z and independent gravity
-g0 z; each magnitude is g0. Zero specific force remains zero. Neither test establishes
real recording conventions. Bare `g` is rejected (Pint gram); standard_gravity is
an explicit acceleration conversion, not an assigned 1 g source value. No rider G,
axis mapping, gravity compensation, frame rotation, filtering, GPS units, timeline
or epoch is calculated. All five originals remain unit-unqualified; Watch gravity
and GPS remain absent. NumPy float64 rounding/underflow does not replace source
precision; exact source bytes remain in the retained ImportSuccess.

## Passive frame math and provisional rider vectors

Opt-in `analysis.frames` requires the locked SciPy analysis extra:

- `OrthonormalFrame(rows)`: three immutable Vector3 target axes expressed in DEVICE
  coordinates. Rejects non-unit/skew/parallel/reflected bases without normalization;
  numerical admission is absolute `1e-10`, relative zero, on orthogonality/determinant.
- `rotate_vectors(samples, frame, *, inverse=False) -> SampleValues`: passive
  `v_target = R @ v_device`, or its inverse. Rows of sample arrays multiply `R.T`.
  This is unit-neutral math; missing rows remain explicit and finite range is checked.
- `RiderCalibration(source_sha256, basis, references)`: explicit source-bound
  exploratory mapping. No constructor infers mounting, yaw or a pose from source vectors.
- `analyze_rider_frame(source, *, calculation_time, calibration=None, profile=None,
  acceleration_contract=None, gravity_contract=None) -> AnalysisResult`: complete M2
  input only. Available vectors require a rider_calibrated profile, `allow_provisional=True`,
  named assumptions, policy references, calibration and independent motion contracts.

Longitudinal/lateral/vertical columns follow the explicit project convention
X forward/Y left/Z rider-up. Every available rider result remains PROVISIONAL;
no API in this stage certifies real rider loading. Without calibration/qualified
units/data, channels are UNAVAILABLE with reasons. Wrong source/profile/opt-in
raises TypeError/ValueError; range defects yield INVALID with FRAME_TRANSFORM_RANGE.
Diagnostics remain deterministic; raw unfiltered quantity/unit/time/source indices
and complete M2 input survive. Profile configuration records source unit/quantity,
NumPy/Pint/SciPy versions and the frame matrix/tolerance; references remain channel evidence.

Example with a separately constructed synthetic basis and source-matching unit contract:

```python
from ride_forces_analyzer.analysis import AnalysisProfile, ProfileName
from ride_forces_analyzer.analysis.frames import RiderCalibration, analyze_rider_frame

profile = AnalysisProfile(
    ProfileName.RIDER_CALIBRATED,
    policy_references=("synthetic passive-basis test protocol",),
    assumptions=("explicit simulated mounting; no real-app qualification",),
    allow_provisional=True,
)
# imported, basis, unit_contract and calculation_time are explicit caller inputs.
calibration = RiderCalibration(imported.source_sha256, basis, ("synthetic basis protocol",))
result = analyze_rider_frame(
    imported,
    calculation_time=calculation_time,
    calibration=calibration,
    profile=profile,
    acceleration_contract=unit_contract,
)
```

All five real fixtures remain unit/frame-unqualified; absent Watch gravity stays
absent. See [ADR 0005](../decisions/0005-passive-frame-transforms.md),
[M3 evidence](../validation/M3.md) and `tests/test_frames.py`. Source-app
references remain required for generic physical calibration. This broader research
is not reduced-M3 acceptance; existing app-reference projection/mean has separate
evidence, and analytical GPS is outside current scope.

## Selected-range extrema

`ride_forces_analyzer.force_extrema.calculate_extrema(source, first, last, *, reference=None, calculation_time=None)`
is a pure typed API with no Qt or optional NumPy requirement for raw use. The module
sits outside the NumPy-backed analysis package so raw fallback remains available.
Pass the current AppReference for calibrated values; its source hash, rate and
channel lengths must match the recording. Raw mode reads original x/y/z; no source
minForce/maxForce is substituted. Intervals are inclusive and must be valid.

Frozen SelectionExtrema/ChannelExtrema/Extremum results retain source identity,
algorithm, aware calculation time, mode/unit/window/capability, effective rate/origin,
interval endpoints/count and each min/max value/index/recording second. Ties use
the earliest source sample. Empty/invalid intervals, mismatched references or
non-finite selected values raise ValueError. Filtering is never repeated at selection
edges. Source arrays/bytes are unchanged.

ExplorerData.selection_extrema delegates calculation; extrema_text formats replay
notation and processing context. The inspector refreshes on load, mode, smoothing
and selection changes, including while the slider is held. Cursor/zoom or hiding
a curve does not change the result. [Reduced M3 acceptance](../validation/M3.md)
records focused tests; this is not a general statistics or physical-calibration API.
