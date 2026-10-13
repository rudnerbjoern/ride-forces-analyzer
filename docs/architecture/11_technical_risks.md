# 11. Risks and Technical Debt

[Architecture index](README.md)

| Risk / debt                      | Known state                                                                                                                | Consequence / next evidence gate                                                                                        |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Unverified motion semantics      | Units, axis polarity, calibration and acceleration convention are unresolved                                               | M3 must cross-check source-app/reference evidence before verified rider-axis output                                     |
| Unverified time / indices        | Epoch, end-index convention and a common motion/GPS clock are unresolved                                                   | Preserve indices/timestamps; no inferred synchronization or chronology claim                                            |
| GPS interpretation               | Negative speed/course/accuracy and suspicious values are preserved with warnings                                           | Units, sentinels and physical plausibility require independent evidence                                                 |
| Device capability differences    | Apple Watch can lack gravity/GPS; present arrays can still be defective                                                    | Never synthesize missing sensors; separate import success from analysis readiness                                       |
| Schema evolution                 | Only 2.2.0 is supported; observed fixtures are not a manufacturer specification                                            | Obtain authorized evidence and explicit adapters/tests before accepting another version                                 |
| Resource / filesystem guarantees | Shape/diagnostic budgets are implemented; total RAM, cold-cache and hostile filesystem/ACL behavior are not fully verified | Retain conservative limits and document benchmark/mock boundaries                                                       |
| GUI and service integration      | Minimal window still displays an M1 placeholder and has no importer connection                                             | Complete later widget/library milestones before claiming interactive import or playback                                 |
| Export and release compatibility | Encoding, alpha-video compatibility, POV timing and clean-VM installation are planned                                      | Verify target editor/codecs and standalone deployment in M6–M8                                                          |
| Dependency security              | The recorded Node dependency audit has an open advisory                                                                    | Follow the dated [security follow-up](../validation/DEPENDABOT.md); do not infer resolution from architecture migration |

M2 parsing/integrity acceptance does not establish sensor accuracy, Ride Forces
algorithm equivalence or suitability for safety-critical interpretation. Resolve
scientific questions through the [M3 plan](../implementation/DEV-REQ-003/PLAN.md)
without changing original source evidence. M2 limitations and historical verification
boundaries remain in the [acceptance report](../validation/M2.md).
