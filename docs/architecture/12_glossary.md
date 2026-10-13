# 12. Glossary

[Architecture index](README.md)

| Term                          | Definition                                                                                                    |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------- |
| .forces                       | Ride Forces JSON export, consumed as read-only original input                                                 |
| Recording                     | Immutable canonical M2 representation of validated available recording data                                   |
| SourceEnvelope                | Owner of exact input bytes, immutable source tree and source provenance                                       |
| SourceNumber                  | Retained JSON number token and exact numeric value, distinct from a numeric string                            |
| Provenance                    | Source identity/path, byte count/hash and origin of interpreted/defaulted data                                |
| Capability                    | Explicit availability of data or, in planned analysis, justified interpretation                               |
| Owner default                 | Rate 50 or riding position Seated applied only to absent source fields, never inserted into source bytes/tree |
| MotionSequence                | Immutable acceleration and optional gravity vectors; sample pairing is structural                             |
| Structural vector             | Retained direction/calibration vector without inferred physical transform                                     |
| GPS slot                      | Original independent GPS sequence position, retained even when no valid typed fix is available                |
| Diagnostic                    | Stable severity/code/pointer/message and optional source index describing a defect without source payloads    |
| JSON Pointer                  | RFC 6901 location within retained JSON, escaped for deterministic diagnostic paths                            |
| ImportSuccess / ImportFailure | Tagged complete-import outcome; failure exposes no Recording                                                  |
| DecodeSuccess                 | Valid supported source envelope; not a complete Recording or analysis claim                                   |
| Qt-independent                | Domain/importer code can run without importing or constructing Qt objects                                     |
| Rider frame                   | Planned physical coordinate frame; its mapping/calibration require evidence                                   |
| Opaque video                  | Planned standalone video with a filled background                                                             |
| Alpha overlay                 | Planned output with transparency, independent of opaque-video output                                          |
| POV                           | Point-of-view ride video, a planned local synchronization input                                               |
| ADR                           | Architecture decision record with rationale and evidence, linked from chapter 09                              |
