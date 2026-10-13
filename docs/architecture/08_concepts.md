# 8. Cross-cutting Concepts

[Architecture index](README.md)

## Source ownership and typed accessors

SourceEnvelope owns exact immutable input bytes and a recursively immutable
JSON tree; a Path is provenance only. Retain original byte count and SHA-256
where complete input is available. Retrieving original bytes is the lossless
round-trip, not JSON re-encoding. Unknown nested fields, order, number tokens,
numeric strings, null, absent properties and GPS values remain distinguishable.
Canonical floating-point accessors never replace original evidence.

## Availability, defaults and scientific boundaries

Device metadata indicates expected data availability, not scientific semantics.
The authorized Apple Watch fixture has acceleration but no gravity/GPS;
missing capabilities stay explicit. iPhone/unknown-profile absence is diagnosed
according to [ADR 0002](../decisions/0002-forces-source-contract.md).

Owner-default sampleRate 50 and ridingPosition Seated apply only when absent,
with source/default provenance and no insertion into the retained source tree.
Invalid present rate fails core validation; invalid present riding position warns
and becomes unavailable. Zero never means absent. A successful acceleration-only
Recording is complete for available input, not proof of rider-analysis eligibility.

Motion indices are bounded independently; Taron's gravityIndex before startIndex
is valid structural evidence, not permission to infer chronology. Structural
vectors are retained without normalization, axis mapping or force calculation.
GPS slots keep their own length/order and source indices, with no alignment to
acceleration. Negative speed/course/accuracy stays raw and warns; defective fixes
retain slots with unavailable typed data. No units, epoch or sentinel interpretation
is asserted. Ordered attributes retain arbitrary source labels and values.

## Strict decoding and resource policy

Strict UTF-8 decoding permits one leading BOM while retaining it in source bytes.
The root must be an object, duplicate keys/non-JSON constants are rejected and
only schema 2.2.0 is dispatched. Iterative preflight bounds bytes, container depth,
array lengths, nodes, object members and string/number-token lengths before
full allocation, including unknown fields. A shared per-call diagnostic budget
bounds validation while records are generated; overflow is fatal.

Actual defaults and configurable ceilings are maintained in
[ImportLimits](../../src/ride_forces_analyzer/importers/limits.py),
[decoder contracts](../development/STRICT_DECODING.md) and ADR 0002.
These budgets do not guarantee peak RAM, CPU time or hostile-filesystem safety.

## Results and diagnostics

ImportSuccess owns a complete immutable Recording; ImportFailure has no Recording
and at least one error. Stable diagnostics carry severity, code, RFC 6901 JSON
Pointer, message and optional source index. Order is error/warning/info, escaped
pointer, then code; ties retain emission order. Messages identify defects without
coordinate values, recording payloads or exception excerpts.

Decoder/core errors fail fast before later stages. Optional defects can warn and
recover if the core remains valid. Caller misuse remains distinct from source
failure. There is no shared recording state or process-global decoder mutation.

## Settings and validation

Bootstrap AppSettings uses immutable strict Pydantic validation with rejected
unknown settings; it is not a recording-schema model. Pylance/Pyright share strict
configuration, mypy checks source and pytest verifies runtime contracts. All five
originals have pinned byte-length/SHA-256 regression guards and full import tests.
Quality workflows and dated evidence are linked from
[chapter 10](10_quality_requirements.md); procedural details stay in development guides.

## Future render concept

Render frames independently of encoding, preserving independent opaque-video and
transparent-overlay outputs. Alpha/video compatibility and time synchronization
need explicit verification before implementing export; see [strategy](04_solution_strategy.md).

## Planned M3 scientific contracts

[DEV-REQ-003](../requirements/DEV-REQ-003-scientific-analysis.md) requires
distinct proper acceleration, measured gravity and kinematic acceleration; no
combination of source sequences is justified by successful M2 parsing. Define
DEVICE, WORLD/GRAVITY and RIDER frames only with documented units, handedness,
sign and transform direction. A scientific ADR/reference gate precedes verified
rider outputs; synthetically correct rotations do not prove source calibration.

Analysis products must retain source hash, algorithm/configuration, quantity,
frame, time basis and raw/filtered provenance. Planned channel states are VERIFIED,
PROVISIONAL, UNAVAILABLE and INVALID. Profiles include a deterministic
raw_device_only baseline and separately approved rider_calibrated, gps_exploratory
and gps_strict policies. Unknown units/missing capabilities are not replaced with
zero, standard gravity or synthetic sensor data.

A future index/rate timeline is labeled INFERRED_UNIFORM and retains source/default
rate provenance; source date/GPS epochs and offsets remain unverified. Keep raw
samples alongside configurable offline filtering, with edge/short-segment and
filter-induced peak changes explicit. Future accepted WGS84 segments yield a
horizontal path estimate, not 3D track length; derived speed requires a verified
time basis. Preserve rejected fixes and negative reported values in M2 evidence.
All these contracts are planned, not implemented M2 interpretation.
