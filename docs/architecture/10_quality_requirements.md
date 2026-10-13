# 10. Quality Requirements

[Architecture index](README.md)

## Quality requirements overview

The top goals are integrity, offline use, deterministic diagnostics, separation
of concerns and honest scientific provenance. Importer NFR-001–007 and AC-01–10
are defined in [DEV-REQ-002](../requirements/DEV-REQ-002-forces-importer.md).
M1/M2 acceptance is verified; M3 scientific criteria remain planned.

## Quality scenarios

| Scenario                                                        | Required response                                                                                | Verification                                           |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| Import any of the five authorized originals                     | Preserve all bytes/GPS/unknown content and available typed data; never write the input           | Integrity, inventory and service tests; M2 AC-01–04    |
| Import the same bytes/policy repeatedly or concurrently         | Equivalent immutable results and ordered diagnostics with independent per-call state             | Service/model/result tests; AC-08–09, NFR-002          |
| Supply malformed, duplicate-key, unsupported or oversized input | Structured deterministic failure within configured resource budgets                              | Decoder and diagnostic-budget tests; AC-05–06, NFR-003 |
| Supply missing/defective optional GPS or weather                | Retain source; warn and expose absence/invalid slots without fabricating samples                 | Optional-data tests; AC-04/07                          |
| Process an installed application recording offline              | No network, writes or Qt import in the public importer                                           | Fresh-process offline/write/Qt guards; AC-08–09        |
| Start the native Windows Qt module                              | Validate settings before construction; show and close the real minimal window normally           | Settings and native GUI tests; M1 acceptance           |
| Request rider-axis interpretation without verified semantics    | Future analysis must declare unverified/unavailable capability instead of scientific certainty   | Planned M3 evidence gates, not implemented M2 analysis |
| Render an opaque video and an alpha overlay                     | Future frame generation and encoding remain independent; transparency works in the target editor | Planned M6/DaVinci Resolve acceptance                  |

## Evidence and performance limits

Exact commands, criterion outcomes and test-to-requirement traceability live in
[M1 validation](../validation/M1.md) and [M2 validation](../validation/M2.md), not
copied runner logs in architecture chapters. [Windows setup](../development/SETUP.md)
provides quality commands; local acceptance precedes publication and selected
PR CI supplies secondary validation.

The recorded M2 Windows benchmark observed Path medians of 128–398 ms and bytes
medians of 181–357 ms for five authorized fixtures after warmup. Traced Python
allocation peaks were 5.8–14.2 MiB and 5.1–12.6 MiB respectively. These are historical
local observations, not thresholds or total-RAM/cold-cache guarantees. See the
[M2 measurements](../validation/M2.md) for methodology and limitations.

## Planned M3 acceptance and architecture consistency

[DEV-REQ-003](../requirements/DEV-REQ-003-scientific-analysis.md) requires analytic
vector/rotation references, unit and filtering tests, WGS84 examples and explicit
app-comparison limits. VAL-006/AC-07 cover all five immutable fixtures: actual GPS
segments on the four iPhone profiles and unavailable GPS/gravity-derived products
on Iron Gwazi. M3 AC-01–10 are not yet verified.

ARC-001–004 require consistent arc42 views, Mermaid diagrams and linked scientific
ADRs before local M3 acceptance/publication. The future M3 report must trace these
requirements alongside numerical/capability criteria. Architecture/documentation
checks alone establish neither scientific correctness nor M3 completion.
