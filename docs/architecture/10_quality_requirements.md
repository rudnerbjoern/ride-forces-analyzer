# 10. Quality Requirements

[Architecture index](README.md)

## Quality requirements overview

The top goals are integrity, offline use, deterministic diagnostics, separation
of concerns and honest scientific provenance. Importer NFR-001–007 and AC-01–10
are defined in [DEV-REQ-002](../requirements/DEV-REQ-002-forces-importer.md).
M1/M2 and reduced M3 acceptance are verified; broader scientific research remains
deferred. [M3 evidence](../validation/M3.md) uses the owner-authorized focused checks.

## Quality scenarios

| Scenario                                                              | Required response                                                                                           | Verification                                                                                                               |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Import any of the five authorized originals                           | Preserve all bytes/GPS/unknown content and available typed data; never write the input                      | Integrity, inventory and service tests; M2 AC-01–04                                                                        |
| Import the same bytes/policy repeatedly or concurrently               | Equivalent immutable results and ordered diagnostics with independent per-call state                        | Service/model/result tests; AC-08–09, NFR-002                                                                              |
| Supply malformed, duplicate-key, unsupported or oversized input       | Structured deterministic failure within configured resource budgets                                         | Decoder and diagnostic-budget tests; AC-05–06, NFR-003                                                                     |
| Supply missing/defective optional GPS or weather                      | Retain source; warn and expose absence/invalid slots without fabricating samples                            | Optional-data tests; AC-04/07                                                                                              |
| Process an installed application recording offline                    | No network, writes or Qt import in the public importer                                                      | Fresh-process offline/write/Qt guards; AC-08–09                                                                            |
| Start the native Windows Qt module                                    | Validate settings before construction; show and close the real explorer window normally                     | Settings and native GUI tests; M1 acceptance                                                                               |
| Request rider-axis interpretation without verified semantics          | Analysis declares provisional/unavailable capability where independent evidence is missing                  | Implemented capability gates; independent physical qualification remains open                                              |
| Render an opaque video and an alpha overlay                           | Future frame generation and encoding remain independent; transparency works in the target editor            | Planned M6/DaVinci Resolve acceptance                                                                                      |
| Construct an analysis contract from caller-owned arrays/configuration | Own immutable data, retain source identity, reject unknown physical units and fabricated capability samples | Implemented Stage 1 [model tests](../../tests/test_analysis_models.py); device/frame/reference workers have separate tests |

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

[DEV-REQ-003](../requirements/DEV-REQ-003-scientific-analysis.md) requires the
existing projection/mean/sign/time contracts, basic selected-range extrema and
retained app-comparison limits. All five originals participate with unchanged
bytes and explicit missing sensors. AC-07 verifies GPS reference-only separation,
not WGS84 geodesics or derived speeds. AC-06 covers the implemented pure extrema API and inspector integration;
reduced M3 is verified by its focused acceptance report.

ARC-001–004 require consistent arc42 views, Mermaid diagrams and linked scientific
ADRs before local M3 acceptance/publication. The future M3 report must trace these
requirements alongside numerical/capability criteria. Architecture/documentation
checks alone establish neither scientific correctness nor M3 completion.

## Implemented device mathematics evidence

`tests/test_device_analysis.py` covers analytic norms, explicit simulated stationary
specific force and gravity, zero specific force, Pint SI/centimeter/foot/standard
gravity conversions, unsupported/unknown units, wrong source/sequence bindings,
missingness, float64 range defects, immutable arrays and deterministic diagnostics.
All five originals are tested with no unit declarations: derived channels are
unavailable and bytes/length/SHA-256/mtime are unchanged. An installed fresh-process
guard verifies device calculations without file/network access or Qt imports.

This supports SCI-004–006, SCI-010–012 and VAL-001/004 in device-only scope.
Existing frame/reference suites supply additional AC-04 evidence. Unit-boundary
tests do not establish reduced AC-06 extrema or real physical source qualification.
Exact native Windows results belong in the linked scoped validation reports.

## Stage 3 frame evidence

`tests/test_frames.py` checks signed analytic bases, non-axis-aligned transforms,
inverses, norm invariance, reflections/skew/degeneracy, owned arrays/missingness,
range failure, explicit opt-in/source bindings and unavailable outputs for all five
originals. Native Windows [Stage 3 results](../validation/M3_STAGE3.md) trace
SCI-003/007–009 and VAL-001–002. This supplies synthetic AC-04 evidence; empirical
calibration and broad ADR 0003 approval are deferred. Reduced-M3 acceptance
is complete with basic extrema and focused Windows evidence; it does not claim
universal physical qualification.

## First raw explorer slice

The owner prioritized a first usable M4 slice before complete scientific acceptance.
`tests/test_explorer.py` checks raw presentation/local indices;
`tests/test_explorer_gui.py` exercises all five originals, complete chart points,
viewport bounds, navigation/selection, cancellation/errors, background responsiveness
and close-during-load. [Windows evidence](../validation/RAW_EXPLORER.md) records the
actual results. This establishes raw inspection, not calibrated rider analysis,
full M4 library functionality, playback or export.

[App-reference evidence](../validation/APP_REFERENCE.md) adds analytic projection/
mean tests, five-file extrema cross-checks, source binding and native GUI raw-switch
verification. Numerical agreement and explicit owner confirmation establish the Manta
app-reference contract. This does not qualify arbitrary imports.

## Reduced-M3 acceptance

Verify deterministic selected-range extrema on all three channels, earliest ties,
single-sample/invalid selections, raw/calibrated units and source/window identity.
Existing mean/projection/sign/time and fixture tests remain relevant. Confirm
representative responsive use rather than introducing a benchmark platform.
Additional filter families, GPS analytics and universal physical calibration are
excluded from current milestone acceptance; keep their limits visible.
