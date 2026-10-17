# DEV-REQ-003 — Reduced M3 implementation plan

<!-- cspell:words Butterworth -->

**Status:** Complete within the reduced scope; [acceptance](../../validation/M3.md). Owner-approved scope is force preparation, existing centered
mean, basic extrema and verified contracts. [Requirements](../../requirements/DEV-REQ-003-scientific-analysis.md)
define acceptance; [roadmap](../../ROADMAP.md) defines milestone status.
No automatic next stage or Git operation is authorized by this plan.

## Current implementation

| Product / API                                                   | State       | Evidence                                                                                                               |
| --------------------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------- |
| Immutable models, source provenance and capability gates        | Implemented | [Model/device verification](../../validation/M3_STAGES.md)                                                             |
| Explicit device norms and Pint conversion                       | Implemented | Model/device verification; source-bound unit declarations required                                                     |
| Strict provisional frame transforms                             | Implemented | [Frame verification](../../validation/M3_STAGE3.md)                                                                    |
| Source-app direction projection and raw fallback                | Implemented | [ADR 0006](../../decisions/0006-app-reference-projection.md), [comparison evidence](../../validation/APP_REFERENCE.md) |
| Odd-window centered mean 1–51, default 11; live control/reset   | Implemented | [Explorer verification](../../validation/RAW_EXPLORER.md)                                                              |
| Replay notation, direction signs and read-only source contracts | Implemented | [Time verification](../../validation/TIME_AXIS.md) and source comparisons                                              |
| Selected-interval minimum/maximum result API                    | Implemented | force_extrema.calculate_extrema and focused regressions                                                                |
| Complete reduced-M3 acceptance                                  | Verified    | [Focused Windows acceptance](../../validation/M3.md)                                                                   |

Existing generic device/frame APIs stay supported; they need no universal physical
calibration for this product scope. Manta default-window evidence is source-bound;
other sources/windows remain provisional. The known Kraken start and Voltron
maximum-display differences are documented limitations, not hidden failures or
mandatory private-algorithm reverse engineering.

## A — Basic extrema (implemented)

Implement a small pure analysis API for the three active channels. Follow
SIG-006/009/010 and AC-03/06: inclusive selection, chosen raw/calibrated window,
count and source endpoints, min/max value/index/time, earliest tie, source/unit/
configuration provenance and immutable output. Compute from the existing full
channel data, with no second filter at selection edges. Never reuse stored
source extrema as calculated results or skip hidden channels.

Verify positive/negative/zero, tied extrema, one-sample selection, invalid/empty
intervals, changed source/window/mode, preserved data and all five originals.
Keep calculations/validation outside Qt. Reuse existing dependencies and modules;
no generic statistics framework, new filter or dependency is needed.

## B — Explorer integration (implemented)

Expose those min/max results for the selected range with clear axis/unit and
raw/calibrated setting context. Use the existing workspace/inspector rather than
adding a separate analytics screen. Changing recording, selection or smoothing
must update results consistently; single-sample readout and chart zoom stay independent.
Verify actual Windows interaction, raw fallback, selection boundaries and live updates.
Numeric calculations stay in A's pure API; Qt only displays/formats results through
presentation helpers. Exact placement can follow the established compact layout.

## C — Reduced-M3 acceptance (verified with focused checks)

Review AC-01–AC-10 against final code and retained applicable evidence. Run focused
checks under the owner's focused-only instruction and reuse only valid unchanged
evidence. Full test suites remain on hold until explicit owner release; do not
claim a fresh full-suite run. The [Windows setup](../../development/SETUP.md) guide
retains commands for a future authorized broader validation. Verify representative responsive
loading, navigation, smoothing and extrema; no elaborate benchmark system is needed.
Retain originals' integrity and known comparison limits.

Create compact `docs/validation/M3.md`: criteria, tested revision/scope/platform,
exact commands/results and limits. Finalize roadmap/status and affected arc42
chapters, then check final documentation and changed Mermaid definitions before
claiming completion. These criteria are verified in the linked focused acceptance
report; future changes need their own affected checks.
No staging, commit, push, PR or merge is included; delivery requires separate
explicit authorization under AGENTS.md. Do not begin playback/export automatically.

## Architecture and deferred scope

Read [arc42 index](../../architecture/README.md) and affected chapters 01/03/04/05/
06/08/09/10/11 for extrema/product changes; update other chapters only if affected.
Keep decision rationale in existing ADRs and implementation steps here.
[Task templates](PROMPTS.md) cover A/B/C only.

Butterworth/median filters, automatic events/threshold durations, mean/RMS/quantiles,
GPS geodesics/speed/altitude analysis, new scientific profiles, general physical
rider calibration and full performance research are outside reduced-M3 acceptance.
Interpolation belongs to separately scoped playback work. GPS import/overview
remains supported solely as coarse spatial reference; no GPS/motion alignment.
Installed NumPy/Pint/SciPy/Pandas and generic APIs are not removed by this scope decision.
