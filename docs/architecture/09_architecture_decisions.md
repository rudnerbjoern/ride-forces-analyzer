# 9. Architecture Decisions

[Architecture index](README.md)

## Accepted decisions

| Record                                                                                           | Status                          | Architectural consequence                                                                                                                                  |
| ------------------------------------------------------------------------------------------------ | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [ADR 0001 — Offline Windows and Python](../decisions/0001-platform.md)                           | Accepted                        | Native Windows/Python/uv/PySide6, validation outside widgets, offline processing and separate analysis/export boundaries                                   |
| [ADR 0002 — Source ownership and import boundaries](../decisions/0002-forces-source-contract.md) | Accepted and implemented for M2 | Immutable original bytes/tree, typed Qt-independent APIs, explicit capabilities/defaults, strict 2.2.0 dispatch, resource limits and optional GPS recovery |

The ADR files preserve rationale, requirement references and historical evidence.
This chapter is the arc42 entry point to those records; do not create a second
architecture overview or duplicate their full contracts here.

## Proposed scientific decision

[ADR 0003 — Scientific semantics and capability gates](../decisions/0003-scientific-semantics-and-capability-gates.md)
is the M3 Stage 0 proposal, with verified M2/fixture observations and a per-channel
qualification matrix. It distinguishes specific force, gravity and kinematic
acceleration, proposes explicit frame conventions and limits unknown units,
yaw, extrema, epochs and negative GPS values. Owner review is pending; the Stage 0
proposal does not qualify real recording semantics. Stage 2 separately implements
device-only norms and Pint conversion with explicit source-specific contracts.
Its reference-collection protocol
precedes definitive rider interpretation. AC-01/AC-08 remain open.

[ADR 0004 — Analysis contracts and scientific library policy](../decisions/0004-analysis-contracts-and-library-policy.md)
records Stage 1 executable model boundaries and the isolated native-Windows
license/compatibility audit and subsequent Stage 2 device/unit boundaries. NumPy
and Pint are locked; SciPy/GeographicLib adoption remains pending, AHRS/pyproj
remain research only. The decision is proposed
for owner review; actual model implementation does not accept scientific mappings
or imply numerical M3 completion.

## Decisions requiring evidence

Source units, proper versus gravity-compensated acceleration, coordinate frames,
calibration, source epochs, GPS sentinels, filtering and interval conventions
remain unresolved. M3 must review evidence and capability gates before promising
rider-axis interpretation; follow the [scientific requirements](../requirements/DEV-REQ-003-scientific-analysis.md)
and [implementation plan](../implementation/DEV-REQ-003/PLAN.md).

Transparent-video codec selection, POV synchronization and standalone packaging
are later decisions, not accepted technology choices implied by package names.
The baseline planned PNG RGBA/opaque-video policy is recorded in
[solution strategy](04_solution_strategy.md).
