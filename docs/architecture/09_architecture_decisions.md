# 9. Architecture Decisions

[Architecture index](README.md)

| Record                                                                                                        | Status                            | Consequence                                                                                |
| ------------------------------------------------------------------------------------------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------ |
| [ADR 0001 — Platform](../decisions/0001-platform.md)                                                          | Accepted                          | Offline native Windows/Python, Qt boundaries and separate rendering/encoding               |
| [ADR 0002 — Import boundary](../decisions/0002-forces-source-contract.md)                                     | Accepted / implemented            | Immutable source, strict schema/budgets, typed outcomes and explicit defaults              |
| [ADR 0003 — General scientific qualification](../decisions/0003-scientific-semantics-and-capability-gates.md) | Deferred proposal                 | Physical quantities/frames need independent evidence; not a reduced-M3 closure gate        |
| [ADR 0004 — Models and libraries](../decisions/0004-analysis-contracts-and-library-policy.md)                 | Proposed policy; APIs implemented | Owned models, explicit unit/device APIs, library/license limits                            |
| [ADR 0005 — Passive frames](../decisions/0005-passive-frame-transforms.md)                                    | Implemented numerical convention  | Strict proper bases and PROVISIONAL-only rider transforms; no real-source mapping          |
| [ADR 0006 — Source-app projection](../decisions/0006-app-reference-projection.md)                             | Adopted display policy            | Normalized source directions, mean, signs/replay and raw fallback with per-source evidence |

ADRs preserve rationale and evidence boundaries; API guides own detailed usage.
No general physical qualification follows from a valid import, synthetic frame
math or the adopted source-app display policy.

Reduced M3 includes projection/mean and basic extrema with explicit limits.
GPS is coarse reference only; extra filters, broad statistics and universal
calibration are deferred. [M3 acceptance](../validation/M3.md) owns verification.

Implemented export choices are ProRes 4444 MOV and independent H.264 MP4 with
manual alignment. Additional outputs, POV synchronization and standalone packaging
need their own concrete decisions; see [export contracts](../implementation/VIDEO_EXPORT.md)
and [roadmap](../ROADMAP.md).
