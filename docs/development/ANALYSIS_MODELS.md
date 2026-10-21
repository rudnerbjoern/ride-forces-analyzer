# Analysis contracts and device primitives

- Package: [`ride_forces_analyzer.analysis`](../../src/ride_forces_analyzer/analysis/).
- Dependencies: locked `analysis` extra; NumPy for models/preparation, Pint for
  device-unit conversion, SciPy for passive frame rotation. Importing models does
  not import Pint, SciPy or GeographicLib. Importers do not load analysis; the
  explorer initializes `AnalysisController` when NumPy is available.
- Separate contracts: source-app projection, qualified DEVICE quantities and
  explicitly provisional rider-frame calculations.
- Decisions: [libraries and API boundaries](../architecture/09_architecture_decisions.md#analysis-models-and-libraries),
  [proposed physical qualification policy](../architecture/09_architecture_decisions.md#physical-qualification).
- Planned features and milestone status: [roadmap](../ROADMAP.md).

## Public model shape

| Model                | Contract                                                                                                                  |
| :------------------- | :------------------------------------------------------------------------------------------------------------------------ |
| `AnalysisProfile`    | Name/schema, frozen scalar configuration, policy/assumption references, explicit provisional permission                   |
| `AnalysisResult`     | Full `ImportSuccess`, profile, provenance, tuple channels, ordered diagnostics, result schema                             |
| `AnalysisChannel`    | Identifier, quantity/unit/frame, capability, source sequence/indices, time basis, processing, samples or exclusion reason |
| `SampleValues`       | Owned float64 bytes, immutable shape/row-validity, fresh read-only NumPy view                                             |
| `UnitAssignment`     | Canonical unit, UNKNOWN/ASSUMED/VERIFIED evidence state and references                                                    |
| `TimeBasis`          | SAMPLE_INDEX/INFERRED_UNIFORM/SOURCE_UNVERIFIED/VERIFIED_SECONDS, optional source rate/origin; epoch only when verified   |
| `AnalysisProvenance` | Original source provenance, engine/algorithm identity, explicit aware UTC calculation time                                |
| `AnalysisDiagnostic` | Stable code, importer severity, message, optional channel/source index                                                    |

- These constructors validate at runtime and own tuple/read-only scalar mappings,
  including when callers pass mutable collections. Typed collection inputs are tuples.
- Schema `1` identifies the API contract; it does not define a serialization format
  or imply interoperability across schema/algorithm versions.

## Unified recording analysis

Module: [`analysis.recording`](../../src/ride_forces_analyzer/analysis/recording.py).
Import its classes explicitly; package exports remain explicit.

- `RecordingAnalysis` is a frozen snapshot: original import, configuration, time,
  force stages, independent orientation, context, events, quality and revision.
- Metadata, ride/location, seating attributes, weather, original marker indices,
  independent GPS and unknown fields remain in `analysis.source.recording`.
  No metadata copy or GPS-to-force alignment is created.
- Stages reuse existing time, unit, immutable-buffer, quality and provenance types.
  Context and events each select exactly one force input: projection or smoothing.

```mermaid
classDiagram
    class RecordingAnalysis {
        sample(index) AnalyzedSample
        validate()
        with_configuration(configuration, revision, calculation_time) RecordingAnalysis
        with_smoothing(window_samples, revision, calculation_time) RecordingAnalysis
    }
    class StageAvailability {
        state: AVAILABLE or UNAVAILABLE
        reason: required when unavailable
    }
    class EventAnalysis {
        status: EVALUATED or NOT_EVALUATED
        events: tuple or None
        reason: required when not evaluated
    }
    RecordingAnalysis --> ImportSuccess : source
    RecordingAnalysis --> AnalysisConfiguration : configuration
    RecordingAnalysis --> AnalysisTime : time
    RecordingAnalysis --> ForceSeries : forces
    RecordingAnalysis --> OrientationSeries : orientation
    RecordingAnalysis --> SampleContext : context
    RecordingAnalysis --> EventAnalysis : events
    RecordingAnalysis --> AnalysisQuality : quality
    RecordingAnalysis ..> AnalyzedSample : assembles on demand
    AnalysisConfiguration --> AnalysisProfile : policy and assumptions
    AnalysisConfiguration --> StageConfiguration : algorithms versions and parameters
    ForceSeries --> ProjectedForces : projected
    ForceSeries --> SmoothedForces : smoothed
    SmoothedForces --> ProjectedForces : shared input
    ProjectedForces --> ImportSuccess : source
    ProjectedForces --> AnalysisTime : correspondence
    ProjectedForces --> SampleValues : immutable channels and validity
    SmoothedForces --> SampleValues : immutable channels, Combined and validity
    ProjectedForces --> StageAvailability : availability
    SmoothedForces --> StageAvailability : availability
    OrientationSeries --> StageAvailability : availability
    SampleContext --> StageAvailability : availability
    OrientationSeries --> ImportSuccess : gravity and vertical direction
    OrientationSeries --> AnalysisTime : correspondence
    OrientationSeries --> SampleValues : immutable tilt and validity
    SampleContext --> ProjectedForces : when projection is selected
    SampleContext --> SmoothedForces : when smoothing is selected
    EventAnalysis --> ProjectedForces : when projection is selected
    EventAnalysis --> SmoothedForces : when smoothing is selected
    EventAnalysis "1" --> "0..*" AirtimeEvent : only when evaluated
    AnalysisTime --> TimeBasis : source rate and inferred time
    AnalysisQuality --> AnalysisDiagnostic : diagnostics
    AnalysisQuality --> AnalysisResult : compatible existing results
```

- Paired context/event arrows denote alternative inputs, not simultaneous inputs.
- Snapshots can share projection while holding different smoothing/context/events.
- Orientation depends on source gravity/vertical direction and its own configuration.
- `sample(index)` assembles immutable scalar values on demand without recalculation,
  a row cache, duplicate arrays or a parent-snapshot reference.

### Availability and validation

| State / operation    | Contract                                                                                                            |
| :------------------- | :------------------------------------------------------------------------------------------------------------------ |
| AVAILABLE            | Calculated payload required; no exclusion reason                                                                    |
| UNAVAILABLE          | Coded reason required; no payload; prerequisites propagate to dependents                                            |
| Row validity         | Separate from stage availability; missing values are not valid zero                                                 |
| NOT_EVALUATED events | `events=None` and reason required                                                                                   |
| EVALUATED events     | Tuple, possibly empty; describes valid observed coverage only                                                       |
| Dirty/pending        | Service status; not a mutable result state                                                                          |
| `AnalysisQuality`    | Aggregated capabilities, diagnostics and compatible results; composition never promotes INVALID or provisional data |
| Stage provenance     | Attributable quality/provenance; smoothing inherits projection units, orientation retains its own units             |

- Unified containers store references without constructor normalization/validation.
  Call `RecordingAnalysis.validate()` for manually assembled snapshots.
- Validation checks types, immutable collections, payload/reason combinations,
  source hashes, calculation provenance, configuration, dependencies, full-length
  buffers and original index/order correspondence. Rate value/provenance and
  replay origin must match the source.
- Validation returns `None`; incompatible types raise `TypeError`, inconsistent
  values/relationships raise `ValueError`. No I/O, buffer copies or scientific certification.
- `prepare_recording_analysis(source, configuration, revision=..., calculation_time=...)`
  prepares and validates a snapshot. Revision is a nonnegative integer; time is aware UTC.
- `sample(index)` returns raw/projected/smoothed values, orientation, prepared context,
  recording/replay seconds, stage availability and applicable diagnostics. Missing
  force/orientation rows or stages return `None`; source data remains unchanged.
- `forces.smoothed.combined` is an immutable scalar buffer; `sample(index).combined_g`
  reads its prepared value or `None` for unavailable/invalid rows. It shares the
  smoothing stage's availability, provisional units, provenance and lifetime.
- Sample errors: `TypeError` for non-integer indices (including bool), `IndexError`
  outside the recording, `ValueError` for a manually assembled index-only snapshot
  without a rate. Time uses the source's inferred rate and start-relative replay origin.

### Numerical stages

One implementation per stage; the service delegates to the same preparation path.
All listed algorithms use version `1`.

| Stage       | Implementation                             | Algorithm                          | Parameters                                                                                |
| :---------- | :----------------------------------------- | :--------------------------------- | :---------------------------------------------------------------------------------------- |
| Projection  | `analysis.projection.project_directions`   | `source-direction-unit-projection` | None                                                                                      |
| Smoothing   | `analysis.smoothing.centered_mean`         | `centered-mean`                    | Odd `window_samples` 1–51; default 11                                                     |
| Orientation | `analysis.orientation.orientation_degrees` | `source-gravity-tilt`              | None                                                                                      |
| Context     | `analysis.airtime.AirtimeContext.prepare`  | `vertical-context`                 | Existing constants omitted or explicitly unchanged                                        |
| Events      | `analysis.events.evaluate_events`          | `airtime-events`                   | Optional; finite overrides from the [event contract](../implementation/AIRTIME_EVENTS.md) |

- Projection preserves supplied vertical/lateral/longitudinal order and signs.
  Admission: Gram-matrix deviation at most `0.003`, positive determinant. Rows are
  normalized and dot-projected, never made orthogonal or repaired into a rotation.
- Smoothing always reads unfiltered projection. Edges shorten and renormalize,
  including recordings shorter than the window. Neither primitive changes time or
  source samples; non-finite numerical results raise `ValueError`, not fills/clamps.
- Combined uses `analysis.smoothing.combined_force`: smooth each original device
  x/y/z axis with the same window, then compute `hypot(mean(x), mean(y), mean(z))`.
  It is prepared with the smoothing stage, reused on sample/export reads and
  recalculated when smoothing changes. It is neither a mean of magnitudes nor
  the norm of projected channels; no selection-edge holding is introduced.
- Missing/inadmissible directions or numerical force-range failures exclude affected
  stages with diagnostics. A usable window can recover a smoothing-range exclusion.
- Orientation is independent of force smoothing/projection. Missing gravity/vertical
  direction excludes it; zero gravity produces NaN, false validity and an indexed diagnostic.
- Context reads `context_input` without filtering graph values again. Its version fixes
  the [presentation heuristic](../implementation/AIRTIME.md); custom thresholds are rejected.
- `events=StageConfiguration("airtime-events", "1")` enables detection. Source-app
  defaults disable it. No configuration, unavailable force input or all-missing
  vertical rows means NOT_EVALUATED; usable input yields ordered, non-overlapping
  episodes, possibly none. Gaps split events and produce diagnostics; recording/gap
  boundaries mark incomplete observations. Categories summarize the strongest
  observed portion, independently of per-sample display labels.
- Unsupported algorithms/versions/parameters, invalid revisions or non-UTC times
  fail with `ValueError`. Unsupported event rules produce a matching service failure.
- Raw profile: all derived stages excluded; originals retained. `RIDER_CALIBRATED`
  requires provisional permission, assumptions and policy references. Source-app
  results retain PROVISIONAL quality, assumed units and source/application/NumPy/time
  provenance; they are not qualified physical RIDER/WORLD_GRAVITY results.

### Recalculation and lifetime

| Operation / change                                                      | Reuse / replacement                                                                                              |
| :---------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------- |
| `with_configuration(configuration, revision=..., calculation_time=...)` | New validated snapshot; reuse requires equal stage configuration and identical actual input objects              |
| `with_smoothing(window_samples, revision=..., calculation_time=...)`    | Retains source, time, projection and orientation; smooths unfiltered projection                                  |
| Context/events                                                          | Replaced only when their selected input or configuration changes; projection consumers survive smoothing changes |
| Profile change                                                          | Invalidates policy-dependent projection and orientation                                                          |
| Unchanged configuration/window                                          | No numerical work; new revision still returned                                                                   |
| Provenance                                                              | Reused stages retain original calculation time; recalculated stages use the supplied time                        |
| Lifetime                                                                | No predecessor reference/configuration history; consumers retain snapshots only as needed                        |

- Reconfiguration requires a strictly increasing integer revision and explicit aware
  UTC time. Invalid requests raise `TypeError`/`ValueError`; previous snapshots remain unchanged.
- `with_configuration` compares stored parameters without normalizing their order
  or omitted defaults. `with_smoothing` recognizes the effective window, including default 11.
- Released configurations may be recomputed. Exports retain their bound snapshots;
  normal reference lifetime releases obsolete buffers. The service owns current
  state, active work and current queued deliveries, not a history cache or executor.
- [Snapshot ownership](../architecture/08_concepts.md#snapshot-lifetime-and-reuse)
  is defined in the architecture.

### Analysis service

Module: [`analysis.service`](../../src/ride_forces_analyzer/analysis/service.py).
The Qt-independent `AnalysisService` owns immutable state, selected import,
monotonic request revisions and service-specific subscription handles.

| API / behavior                                | Contract                                                                                                                                                              |
| :-------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `get_state`                                   | Coherent current state, retained snapshot and pending/failure status                                                                                                  |
| `subscribe`                                   | Coordinated registration/state capture; immediate initial delivery precedes later notifications, including reentrant requests                                         |
| `unsubscribe`                                 | Idempotent; removes queued work; an executing callback may finish; handle identity prevents cross-service removal                                                     |
| `request_analysis`                            | Synchronous calculation in caller thread, outside state lock                                                                                                          |
| `request_configuration` / `request_smoothing` | Use selected source, including after failure; reuse compatible stages; no-op advances revision                                                                        |
| Request completion                            | PENDING/`AnalysisInvalidated` → READY/`AnalysisUpdated` or FAILED/`AnalysisFailed`                                                                                    |
| Failure                                       | Retains last complete snapshot with its original source/configuration/revision                                                                                        |
| Expected unavailable stages                   | READY raw-capable snapshot, not request failure                                                                                                                       |
| Caller errors                                 | Wrong top-level source/configuration types raise `TypeError`; calculation/configuration failures terminate the assigned revision with a diagnostic                    |
| `close`                                       | Idempotent; advances revision, clears owned source/snapshot/subscriptions/queues; prevents running work from publishing; independent export snapshots remain readable |

- Stage interests filter numerical notifications. Initial state and terminal status
  matching observed pending work bypass the filter, including superseded queued
  results without interested-stage changes. Dirty stages include dependent forces/context/events.
- Superseded success/failure cannot replace current state. New requests release older
  queued notifications; completed requests may coalesce detailed pending indications.
- Delivery is serialized per registration; different registrations may progress
  concurrently. Callbacks run outside the lock; ordinary callback exceptions are
  logged and remove only that registration. Duplicate callbacks have independent handles.
- [`AnalysisController`](../../src/ride_forces_analyzer/ui/analysis.py) owns workers
  and guarded UI delivery. The [runtime sequence](../architecture/06_runtime_view.md#explorer-analysis-delivery)
  defines initial state, stale/failure handling and subscription cleanup.

### Explorer, exports and storage

| Consumer / API                                 | Contract                                                                                                                                      |
| :--------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------- |
| `ExplorerData`                                 | Presentation state plus bound `analysis`; calibrated channels are read-only NumPy views sharing snapshot buffers, raw channels are tuples     |
| `calibration_available` / `calibrated_enabled` | Prepared force availability / selected presentation mode                                                                                      |
| `with_analysis`                                | Preserves import; checks source object identity                                                                                               |
| `with_calibration`                             | Switches raw/calibrated presentation without numerical work                                                                                   |
| `smoothing_window` / `with_smoothing`          | Read recipe / delegate synchronous partial recalculation; live UI uses controller workers                                                     |
| Sample cards/technical values                  | `analysis.sample(index)`; unavailable calibrated rows never fall back to raw values                                                           |
| Context label/strip                            | Format prepared categories without reclassification                                                                                           |
| Extrema                                        | Read shared smoothed buffers with retained quality/provenance                                                                                 |
| `prepare_export` / `build_previews`            | Require `RecordingAnalysis`, not explorer objects; UI captures snapshot before scheduling work                                                |
| `csv_export.export_csv`                        | Require bound `RecordingAnalysis`; serialize sample views, missingness and quality over an inclusive range                                    |
| `ExportTimeline` / `ExportValues`              | Retain bound snapshot / expose shared scalar buffers as read-only sequences, with `None` for invalid rows                                     |
| `prepare_export_analysis`                      | Equal configuration returns the identical snapshot; otherwise partial recalculation                                                           |
| Presets/jobs                                   | Require full versioned `analysis_configuration`, matching window and all serialized aspect/language/dependency fields; no source bytes/arrays |
| `make_job` / batches                           | Snapshot input / direct import, source-hash check, saved full-history recipe prepared through service before interval binding                 |

- Channel consumers must handle tuple/NumPy-view union; tuple equality and `.index`
  are not shared APIs. Navigation, zoom, display mode, language and appearance do
  not recalculate analysis.
- Layouts consume `ExportTimeline`. Layout, language, frame rate, resolution and
  interval changes do not prepare numerical stages again. All five previews share
  one snapshot; exports retain it independently of workspace/preset changes.
- Bounds use the selected interval; orientation/context use full source history.
  Fractional context lookup floors the source position; numerical values use linear
  interpolation with existing missing-data rules.
- Incomplete stored records are rejected; no format migration or destructive cleanup.

## Raw values and qualified quantities

- `AnalysisProfile()` defaults to `raw_device_only`, with no processing configuration
  or assumptions. SOURCE_VALUES/RAW permits UNKNOWN units. VERIFIED raw means an
  established data contract, not qualified acquisition semantics, physical axes or rider G.
- Original source: `result.source.recording.source`; importer warnings:
  `result.source.diagnostics`. DEVICE labels retain source x/y/z, not Earth/rider axes.
- Canonical units: SPECIFIC_FORCE/GRAVITY/KINEMATIC_ACCELERATION/DEVICE_VECTOR_MAGNITUDE
  → `m/s^2`; LOAD_FACTOR → dimensionless; DISTANCE/ALTITUDE → `m`; SPEED → `m/s`;
  ANGLE → `deg`. Available physical quantities cannot use UNKNOWN units.
- VERIFIED physical values require VERIFIED unit references. ASSUMED units require
  PROVISIONAL channels, explicit opt-in profile and named assumptions. Reference
  strings are caller attestations, not automatic source qualification.
- Interpreted frames require references. Numerical convention is right-handed/passive;
  physical yaw/pose mapping remains unqualified. No real fixture is assigned qualified
  physical units or a qualified RIDER/WORLD_GRAVITY mapping.
- Pint `g` means gram. Loading ratio is dimensionless; acceleration conversion uses
  explicit standard-gravity normalization, never ambiguous `g`.
- UNAVAILABLE/INVALID channels have no samples/indices and require a reason.
  Available missing rows require NaN and false validity; valid zero requires a finite
  sample and true validity. No finite placeholder, infinity, inferred missingness or
  recovery math. Diagnostics must keep partial missingness explicit.
- Indices and indexed diagnostics are bounded against their own acceleration,
  gravity or GPS sequence. Missing Iron Gwazi gravity/GPS cannot be referenced by
  available channels. Validation neither aligns clocks nor changes original markers.

## Immutability and determinism

- `SampleValues` copies numeric input into little-endian float64 bytes; no writable
  ndarray alias survives. Source precision/types remain in the immutable import.
- `samples.values` returns a fresh read-only view; WRITEABLE cannot be enabled.
  Caller metadata changes cannot affect stored shape/dtype or later accessors.
  `values.copy()` is independent and mutable.
- Diagnostics sort ERROR/WARNING/INFO, channel ID, source index (rows without an index first),
  then code. Exact-key ties preserve emission order. Messages exclude raw GPS/payloads.
- Result validity: INVALID for error diagnostics/invalid channels; RESTRICTED for
  provisional/unavailable channels; otherwise VALID. Structural validity is not
  scientific accuracy. Model/preparation callers supply explicit UTC calculation time.

## Model-only construction example

Copies a typed source component; no physical calculation. `calculation_time` is
an explicit caller-supplied aware UTC time, not the recording epoch.

```python
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
            calculation_time,
        ),
        (channel,),
    )
```

## Verification and scope

```powershell
uv run --locked pytest tests/analysis/test_models.py
```

- Model tests: alias/ownership, immutable views, missing versus zero, unit/frame/profile
  gates, provenance/time, deterministic diagnostics, independent indices and all five originals.
- Fresh-process construction: no file/network access, Qt or optional SciPy/Pint/GeographicLib import.
- Preparation/recalculation: numerical primitives, sample views, shared-stage identity,
  calculation calls, unchanged retained export values and snapshot lifetime.
- Service: initial/terminal state, filters, reentrant calls, competing requests, stale
  success/failure, shutdown, callback isolation and ownership. [Coverage](CODE_QUALITY.md#recording-model-and-service-coverage)
  reports model/service modules and enforces the configured minimum.
- [Source-app evidence tests](../../tests/analysis/test_source_app_evidence.py):
  original-file extrema and independent replay screenshots, including Kraken/Voltron
  differences. Synthetic contracts and these comparisons do not qualify real physical
  semantics or event rules. [Source evidence](../validation/APP_REFERENCE.md) remains separate.
- No GPS analytics, clock alignment or physical calibration qualification is performed.

## Device-only vectors and units

Opt-in module: [`analysis.device`](../../src/ride_forces_analyzer/analysis/device.py);
requires NumPy and Pint from the locked `analysis` extra.

- `MotionUnitContract(source_sha256, source_sequence, unit, quantity, unit_evidence, quantity_evidence)`:
  immutable source-specific attestations; separate nonempty unit/meaning references.
  Units: SI, CENTIMETERS, FEET, STANDARD_GRAVITY. Quantities: SPECIFIC_FORCE, GRAVITY,
  KINEMATIC_ACCELERATION.
- `convert_device_vectors(samples, contract) -> SampleValues`: common-unit x/y/z to
  SI; owned bytes/validity retained. Validates contract/shape, not source binding;
  caller must enforce binding.
- `device_vector_norm(channel) -> AnalysisChannel`: VERIFIED raw DEVICE SI x/y/z
  to separate DEVICE_VECTOR_MAGNITUDE; stable Euclidean NumPy norm, no frame transform
  or acceleration/gravity relationship.
- `analyze_device_vectors(source, *, calculation_time, acceleration_contract=None, gravity_contract=None) -> AnalysisResult`:
  complete `ImportSuccess`, source/sequence binding, independent vector/norm channels,
  aware UTC time. `device_vectors` profile retains original units/meanings and library
  versions; channels retain evidence/indices and complete source provenance.
- Missing data/units → UNAVAILABLE, `SOURCE_SEQUENCE_ABSENT`/`SOURCE_UNIT_UNKNOWN`.
  Contract/hash/type defects → `ValueError`/`TypeError`. Finite-range defects → INVALID,
  `UNIT_CONVERSION_RANGE`/`DEVICE_NORM_RANGE`; usable vectors survive norm overflow.
- Source diagnostics, GPS, unknown fields, numeric strings and extrema remain intact.
  Float64 rounding/underflow does not replace exact source bytes.

Synthetic example: common SI components and specific-force meaning are established
independently for that source; `calculation_time` is caller-supplied aware UTC.

```python
from ride_forces_analyzer.analysis import QuantityKind, SourceSequence
from ride_forces_analyzer.analysis.device import (
    DeviceAccelerationUnit,
    MotionUnitContract,
    analyze_device_vectors,
)

# imported is full ImportSuccess; these references must concern that exact source.
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
    calculation_time=calculation_time,
    acceleration_contract=contract,
)
```

- Synthetic stationary specific force `+g0 z` and independent gravity `−g0 z` each
  have magnitude `g0`; zero specific force stays zero. This establishes no real-app convention.
- Bare `g` is rejected; `standard_gravity` is an acceleration conversion, not an
  assigned 1 g source value. No rider G, axis mapping, gravity compensation, rotation,
  filtering, GPS units, timeline or epoch is calculated. All five originals remain
  unit-unqualified; Watch gravity/GPS remain absent.

## Passive frame math and provisional rider vectors

Opt-in module: [`analysis.frames`](../../src/ride_forces_analyzer/analysis/frames.py);
requires the locked SciPy analysis extra.

- `OrthonormalFrame(rows)`: three immutable Vector3 target axes in DEVICE coordinates.
  Rejects non-unit/skew/parallel/reflected bases without repair; orthogonality and
  determinant tolerance absolute `1e-10`, relative zero. Matrix access returns an independent array.
- `rotate_vectors(samples, frame, *, inverse=False) -> SampleValues`: passive
  `v_target = R @ v_device`; array rows multiply `R.T`; inverse uses inverse rotation.
  Unit-neutral; missingness retained, finite range checked.
- `RiderCalibration(source_sha256, basis, references)`: explicit source-bound
  exploratory mapping; no inferred mounting, yaw or pose.
- `analyze_rider_frame(source, *, calculation_time, calibration=None, profile=None, acceleration_contract=None, gravity_contract=None) -> AnalysisResult`:
  complete import. Available vectors require `rider_calibrated`, `allow_provisional=True`,
  named assumptions, policy references, calibration and independent motion contracts.
- Columns: longitudinal/lateral/vertical = X forward/Y left/Z rider-up. Available
  rider results remain PROVISIONAL. Missing prerequisites → UNAVAILABLE with reasons;
  wrong source/profile/opt-in → `TypeError`/`ValueError`; numerical range defects →
  INVALID with `FRAME_TRANSFORM_RANGE`.
- Retain raw unfiltered quantity/unit/time/indices and complete import. Configuration
  records source unit/quantity, NumPy/Pint/SciPy versions and matrix/tolerance;
  references remain channel evidence. Diagnostics retain deterministic ordering.

Synthetic example with explicit caller-provided basis, matching unit contract and time:

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

All five originals remain unit/frame-unqualified; missing Watch gravity stays absent.
See [passive-frame decision](../architecture/09_architecture_decisions.md#passive-frame-transforms),
[scientific gates](../architecture/08_concepts.md#scientific-provenance-and-gates)
and [frame tests](../../tests/analysis/test_frames.py). Generic physical calibration
still requires independent source-app evidence; source-app projection/mean remains
a separate contract.

## Selected-range extrema

API: `ride_forces_analyzer.force_extrema.calculate_extrema(source, first, last, *, forces=None, calculation_time=None)`.
Pure typed API outside the analysis package; raw use needs neither Qt nor NumPy.

| Input / result          | Contract                                                                                                                                                                                    |
| :---------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `forces=None`           | Original raw x/y/z; never source `minForce`/`maxForce` metadata                                                                                                                             |
| `forces=SmoothedForces` | Available full-length channels/validity/provenance; same import, original indices and rate                                                                                                  |
| Interval                | Inclusive, bounded, ordered; ties select earliest source index; no filtering at selection edges                                                                                             |
| Calculation time        | Aware caller time; defaults to current UTC time                                                                                                                                             |
| Errors                  | `ValueError` for invalid/empty intervals/time, mismatched/unavailable stages, incomplete buffers or missing/non-finite selected values                                                      |
| Results                 | Frozen `SelectionExtrema`/`ChannelExtrema`/`Extremum`: source, algorithm, calculation time, mode/unit/window/capability, rate/origin, interval/count, min/max value/index/recording seconds |
| Quality/provenance      | Calibrated results retain actual stage objects and provisional capability; raw results have neither derived object                                                                          |

- Source arrays/bytes remain unchanged. Source-app agreement does not promote
  calibrated extrema to qualified physical values.
- `ExplorerData.selection_extrema` delegates calculation; `extrema_text` formats
  replay/processing context. Default plain text; `rich=True` adds aligned per-channel
  HTML tables with replay, sample and recording-time details.
- Inspector maps visible time through `select_visible`; refreshes on load, zoom,
  mode and smoothing, including held slider changes. Cursor, From/To selection and
  curve visibility do not change extrema.
- Scope: selected-range extrema, not general statistics or physical calibration.
