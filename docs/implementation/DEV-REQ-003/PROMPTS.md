# Scoped task templates — reduced M3

Use one task after explicit authorization. [PLAN.md](PLAN.md) and
[DEV-REQ-003](../../requirements/DEV-REQ-003-scientific-analysis.md) define the current
scope and acceptance. Implemented projection/mean/device/frame work is not restarted.

## Shared constraints

Read AGENTS.md, roadmap, requirements/plan and relevant arc42 chapters once per
working context. Preserve every original byte, source metadata and missing sensor.
Keep analysis/validation outside widgets; reuse locked dependencies and current
contracts. Retain raw/calibrated distinction, source/window/time provenance,
known comparison discrepancies and GPS reference-only use. Verify affected
behavior on native Windows, report compact evidence and stop at the assigned scope.
These templates grant no Git delivery permission.

## A — Extrema API

Implement deterministic min/max for each of the three active channels over an
inclusive sample selection, with value/index/time, count, source/unit/configuration
identity and earliest tie handling. Use existing full channels; do not filter at
selection edges or substitute stored source extrema. Add meaningful pure regression
tests including one-sample/invalid selections and all five originals. No additional
statistics engine, filter family, GPS calculations or dependencies.

## B — Explorer display

Display A's selected-range extrema in the established workspace, clearly labeled
by axis/unit and current raw/calibrated mode. Update on source/selection/smoothing
changes without changing cursor/zoom. Keep calculation and validation in the pure
API/presentation boundary. Verify actual native Windows interaction and compact layout.

## C — Acceptance

Verify every current AC-01–AC-10 against implementation and valid evidence, complete
required Windows checks and compact docs/validation/M3.md, update roadmap/arc42 and
check final docs/diagram syntax. Record known limitations without claiming universal
physical calibration. Missing criteria leave M3 open. Do not start playback/export
or any Git delivery automatically.
