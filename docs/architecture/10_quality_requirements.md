# 10. Quality Requirements

[Architecture index](README.md)

Integrity, offline use, deterministic diagnostics, separation of concerns and
explicit scientific provenance are the primary quality goals.

| Scenario                                                | Required response                                                                 | Verification ownership                                                                                           |
| :------------------------------------------------------ | :-------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------- |
| Import authorized originals or unknown extension fields | Preserve exact bytes and all data; never write inputs                             | Fixture, source-model and importer suites; [import contract](08_concepts.md#source-ownership-and-validation)     |
| Repeat/concurrently import the same bytes/policy        | Equivalent immutable results and ordered independent diagnostics                  | Service/result suites                                                                                            |
| Malformed, unsupported or oversized input               | Structured failure within configured budgets                                      | Decoder/motion/diagnostic suites                                                                                 |
| Missing/defective optional data                         | Retain source and distinguish absent/invalid values from zero                     | Optional-parser suites                                                                                           |
| Installed offline processing                            | No cloud dependency or writes to originals                                        | Fresh-process guards                                                                                             |
| Scientific calculations                                 | Explicit source/unit/frame gates, owned results and reproducible mathematics      | Model/device/frame/reference/extrema suites; [analysis contract](08_concepts.md#scientific-provenance-and-gates) |
| Unqualified real sensor interpretation                  | Preserve provisional/unavailable status and known discrepancies                   | [Source comparisons](../validation/APP_REFERENCE.md)                                                             |
| Desktop interaction                                     | Responsive load/navigation, bounded zoom, reachable wide/compact controls         | Explorer/native GUI suites; [explorer contract](../implementation/RAW_EXPLORER.md)                               |
| Change UI language or theme                             | Readable text and preserved data/view state                                       | Theme/i18n GUI suites; [localization contract](../development/LOCALIZATION.md)                                   |
| Render opaque/transparent output                        | Separate frames/encoding, complete geometry/alpha, exclusive publication          | Rendering/preview/encoder suites; [encoder compatibility boundary](07_deployment_view.md#encoder-installation)   |
| Reopen/run saved batches                                | Durable snapshots, hash checks, independent failures and cooperative cancellation | Storage/batch suites; [batch contract](../implementation/EXPORT_BATCHES.md)                                      |

The maintained regression suites verify current contracts rather than archived
milestone identifiers. Keep arc42 views consistent, decisions documented and diagrams checked.
Numerical correctness alone does not qualify physical sensor semantics.

[Windows setup](../development/SETUP.md) owns exact quality commands.
Native local acceptance precedes publication; PR CI is secondary validation.
Active validation reports retain necessary scientific/security/release evidence;
superseded milestone reports and delivery transcripts are not maintained.
Run focused checks first; full suites follow owner authorization under AGENTS.md.

Import benchmarks are local observations, not throughput, total-RAM or cold-cache
guarantees. Universal physical calibration, analytical GPS, extra filters and broad
statistics are excluded from reduced M3. Clean-machine release and a manually
inspected Onride composite remain separate acceptance areas.
