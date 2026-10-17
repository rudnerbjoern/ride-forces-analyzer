# 9. Architecture Decisions

[Architecture index](README.md)

## Accepted decisions

| Record                                                                                           | Status                          | Architectural consequence                                                                                                                                  |
| ------------------------------------------------------------------------------------------------ | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [ADR 0001 — Offline Windows and Python](../decisions/0001-platform.md)                           | Accepted                        | Native Windows/Python/uv/PySide6, validation outside widgets, offline processing and separate analysis/export boundaries                                   |
| [ADR 0002 — Source ownership and import boundaries](../decisions/0002-forces-source-contract.md) | Accepted and implemented for M2 | Immutable original bytes/tree, typed Qt-independent APIs, explicit capabilities/defaults, strict 2.2.0 dispatch, resource limits and optional GPS recovery |

The ADR files preserve rationale, requirement references and scoped evidence.
This chapter is the arc42 entry point to those records; do not create a second
architecture overview or duplicate their full contracts here.

## Deferred general scientific research

[ADR 0003 — Scientific semantics and capability gates](../decisions/0003-scientific-semantics-and-capability-gates.md)
is a deferred general-scientific proposal, with verified M2/fixture observations and a per-channel
qualification matrix. It distinguishes specific force, gravity and kinematic
acceleration, proposes explicit frame conventions and limits unknown units,
yaw, extrema, epochs and negative GPS values. Owner review is pending; the Stage 0
proposal does not qualify real recording semantics. Stage 2 separately implements
device-only norms and Pint conversion with explicit source-specific contracts.
Its reference-collection protocol
precedes any future definitive physical rider interpretation. It is not a
reduced-M3 closure gate; current acceptance is defined by DEV-REQ-003.

[ADR 0004 — Analysis contracts and scientific library policy](../decisions/0004-analysis-contracts-and-library-policy.md)
records Stage 1 executable model boundaries and the isolated native-Windows
license/compatibility audit and subsequent Stage 2 device/unit boundaries. NumPy
and Pint are locked; Stage 3 additionally adopts SciPy while GeographicLib remains
outside reduced M3. AHRS/pyproj
remain research only. The decision is proposed
for owner review; actual model implementation does not accept scientific mappings
or imply numerical M3 completion.

## Decisions requiring evidence

Source units, proper versus gravity-compensated acceleration, coordinate frames,
calibration, source epochs, GPS sentinels, filtering and interval conventions
remain open for general physical qualification. ADR 0006 separately records adopted
source-app display semantics and per-source comparison evidence. M3 must review evidence and capability gates before promising
rider-axis interpretation; follow the [scientific requirements](../requirements/DEV-REQ-003-scientific-analysis.md)
and [implementation plan](../implementation/DEV-REQ-003/PLAN.md).

Transparent-video codec selection, POV synchronization and standalone packaging
are later decisions, not accepted technology choices implied by package names.
The baseline planned PNG RGBA/opaque-video policy is recorded in
[solution strategy](04_solution_strategy.md).

## Implemented Stage 3 numerical convention

[ADR 0005 — Passive frames and exploratory rider gate](../decisions/0005-passive-frame-transforms.md)
records the separately instructed numerical convention, SciPy adoption, strict
basis admission and PROVISIONAL-only rider output. It accepts no physical mapping
of the originals and does not resolve or approve the scientific proposals in ADR 0003.

[ADR 0006 — Source-bound app-reference projection](../decisions/0006-app-reference-projection.md)
records the owner-confirmed Manta direction projection, explicit norm correction
for rounded directions, configurable mean (default 11) and raw-view fallback. Strict rotation
contracts remain unchanged. Calibrated display is enabled for all usable imports;
per-source qualification, provenance and raw fallback remain explicit.

## Current product acceptance boundary

The owner-approved [reduced M3 scope](../requirements/DEV-REQ-003-scientific-analysis.md)
uses ADR 0006 and the existing mean/projection contracts, basic per-axis extrema
and explicit limitations. Broad ADR 0003 scientific qualification is deferred,
not a gate to reduced-M3 completion. GPS is coarse reference only; GeographicLib,
additional scientific filters/events and universal physical calibration are not
required. Existing device/frame APIs and their stricter gates remain supported.
