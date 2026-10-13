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
