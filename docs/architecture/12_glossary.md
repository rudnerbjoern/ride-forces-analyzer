# 12. Glossary

[Architecture index](README.md)

| Term                          | Definition                                                                                     |
| ----------------------------- | ---------------------------------------------------------------------------------------------- |
| .forces                       | Read-only JSON recording exported by Ride Forces or the supported RFDB profile                 |
| .zforces                      | Raw-DEFLATE-compressed Ride Forces recording; original compressed bytes remain source evidence |
| ADR                           | Architecture decision with rationale and evidence, retained in chapter 09                      |
| Alpha overlay                 | ProRes 4444 MOV output with transparency for compositing                                       |
| AnalysisProfile               | Immutable policy/configuration and explicit provisional permission                             |
| AnalysisResult                | Immutable explicit device/frame result retaining its complete import and provenance            |
| AnalysisService               | Qt-independent current state, revisions and subscriptions                                      |
| Capability                    | Per-channel availability and evidence status                                                   |
| DecodeSuccess                 | Valid supported source envelope; not a complete import or analysis result                      |
| Diagnostic                    | Severity, stable code, JSON Pointer, message and optional original sample index                |
| ExportTimeline                | Bound analysis snapshot, source interval and deterministic video clock                         |
| GPS slot                      | Original GPS sequence position, retained even without a usable typed fix                       |
| ImportSuccess / ImportFailure | Complete-import result; failure exposes no Recording                                           |
| JSON Pointer                  | RFC 6901 field location in the retained source                                                 |
| Layout                        | Export graphic design; owns its instruments, arrangement, geometry and supported placements    |
| MotionSequence                | Acceleration and optional gravity vectors; pairing establishes structure, not physical meaning |
| Opaque video                  | H.264 MP4 output with a filled background                                                      |
| Owner default                 | Rate 50 or Seated posture applied only to absent fields, without rewriting source data         |
| POV                           | Point-of-view ride footage aligned in external video-editing software                          |
| Provenance                    | Source identity and the origin of values, defaults and calculations                            |
| Qt-independent                | Usable without constructing or importing Qt widgets                                            |
| Recording                     | Immutable canonical representation of validated recording data                                 |
| RecordingAnalysis             | Immutable shared snapshot of source, time and prepared analysis stages                         |
| Rider frame                   | Explicit rider coordinate frame whose physical mapping requires independent evidence           |
| SampleValues                  | Owned float64 bytes, validity mask and read-only NumPy views                                   |
| SourceEnvelope                | Owned original bytes, immutable source tree and provenance                                     |
| SourceNumber                  | Exact JSON number token/value, distinct from a numeric string                                  |
| Structural vector             | Retained direction/calibration vector without an inferred physical transform                   |
| Theme                         | UI color scheme; controls the application's appearance                                         |
| VERIFIED channel              | Verified only for its declared scope; raw-data verification does not qualify rider loading     |

`OrthonormalFrame` stores right-handed target axes as rows in DEVICE coordinates.
`RiderCalibration` binds an explicit provisional basis to a source hash; neither
type certifies real rider loading.
