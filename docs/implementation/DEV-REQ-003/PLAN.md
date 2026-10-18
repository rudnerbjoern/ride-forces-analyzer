# Reduced M3 scope and acceptance

**Complete within the owner-approved scope.**
[Requirements](../../requirements/DEV-REQ-003-scientific-analysis.md) define
AC-01–AC-10; [acceptance](../../validation/M3.md) records their verification.

## Implemented boundary

- Immutable source-bound analysis models and capability/provenance gates.
- Explicit device norms/Pint conversions and strict provisional frame transforms.
- Source-app direction projection, raw fallback and configurable centered mean.
- Replay sample notation and source-app directional signs.
- Pure selected-range extrema for all three active channels: inclusive bounds,
  earliest tie, value/index/time and source/unit/window provenance.
- Inspector integration that refreshes on source, selection, mode or smoothing
  changes; cursor, zoom and hidden curves do not change the calculation.

[ADR 0006](../../decisions/0006-app-reference-projection.md) defines the product
projection policy; generic device/frame APIs retain their separate gates.
[Source comparisons](../../validation/APP_REFERENCE.md) retain Manta confirmation,
Kraken's start mismatch and Voltron's displayed-maximum difference.

## Acceptance boundary

Verify analytic norms/projections/rotations, every allowed mean window and edge
handling, immutable results, invalid/single-sample/tied selections, all five
originals, raw fallback, offline processing and responsive Windows interaction.
Compute extrema from existing full channels without refiltering selection edges.
Keep calculations outside Qt and update the existing arc42 views.

Additional filters, events/threshold durations, broad statistics, universal
physical rider calibration and analysis benchmark research are deferred.
GPS remains independent coarse spatial context; geodesics/speed/altitude analysis
is excluded. Interpolation needs a separate playback requirement.
No new numerical dependency or general statistics framework is required.

Further work and delivery require separate authorization under
[AGENTS.md](../../../AGENTS.md); this completed scope is not an execution queue.
