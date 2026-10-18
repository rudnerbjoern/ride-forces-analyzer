# 10. Quality Requirements

[Architecture index](README.md)

Integrity, offline use, deterministic diagnostics, separation of concerns and
explicit scientific provenance are the primary quality goals.

| Scenario                                                | Required response                                                                 | Verification ownership                                                   |
| ------------------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Import authorized originals or unknown extension fields | Preserve exact bytes and all data; never write inputs                             | Fixture, source-model and importer suites; [M2](../validation/M2.md)     |
| Repeat/concurrently import the same bytes/policy        | Equivalent immutable results and ordered independent diagnostics                  | Service/result suites                                                    |
| Malformed, unsupported or oversized input               | Structured failure within configured budgets                                      | Decoder/motion/diagnostic suites                                         |
| Missing/defective optional data                         | Retain source and distinguish absent/invalid values from zero                     | Optional-parser suites                                                   |
| Installed offline processing                            | No cloud dependency or writes to originals                                        | Fresh-process guards                                                     |
| Scientific calculations                                 | Explicit source/unit/frame gates, owned results and reproducible mathematics      | Model/device/frame/reference/extrema suites; [M3](../validation/M3.md)   |
| Unqualified real sensor interpretation                  | Preserve provisional/unavailable status and known discrepancies                   | [Source comparisons](../validation/APP_REFERENCE.md)                     |
| Desktop interaction                                     | Responsive load/navigation, bounded zoom, reachable wide/compact controls         | Explorer/native GUI suites; [explorer](../validation/RAW_EXPLORER.md)    |
| Change UI language or theme                             | Readable text and preserved data/view state                                       | Theme/i18n GUI suites; [localization](../validation/LOCALIZATION.md)     |
| Render opaque/transparent output                        | Separate frames/encoding, complete geometry/alpha, validated publication          | Rendering/preview/encoder suites; [video](../validation/VIDEO_EXPORT.md) |
| Reopen/run saved batches                                | Durable snapshots, hash checks, independent failures and cooperative cancellation | Storage/batch suites; [batches](../validation/EXPORT_BATCHES.md)         |

Requirements retain their acceptance identifiers:
[importer](../requirements/DEV-REQ-002-forces-importer.md) and
[reduced analysis](../requirements/DEV-REQ-003-scientific-analysis.md).
ARC-001–004 require consistent arc42 views, linked ADRs and checked diagrams.
Numerical correctness alone does not qualify physical sensor semantics.

[Windows setup](../development/SETUP.md) owns exact quality commands.
Native local acceptance precedes publication; PR CI is secondary validation.
Reports scope verified content/platform and known limits without duplicating logs.
Only focused checks are currently authorized.

Import benchmarks are local observations, not throughput, total-RAM or cold-cache
guarantees. Universal physical calibration, analytical GPS, extra filters and broad
statistics are excluded from reduced M3. Clean-machine release and a manually
inspected Onride composite remain separate acceptance areas.
