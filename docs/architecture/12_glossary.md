# 12. Glossary

[Architecture index](README.md)

| Term                          | Definition                                                                                     |
| ----------------------------- | ---------------------------------------------------------------------------------------------- |
| .forces                       | Read-only JSON recording exported by Ride Forces or the supported RFDB profile                 |
| .zforces                      | Raw-DEFLATE-compressed Ride Forces recording; original compressed bytes remain source evidence |
| Recording                     | Immutable canonical representation of validated recording data                                 |
| SourceEnvelope                | Owned original bytes, immutable source tree and provenance                                     |
| SourceNumber                  | Exact JSON number token/value, distinct from a numeric string                                  |
| Provenance                    | Source identity and the origin of values, defaults and calculations                            |
| Capability                    | Per-channel availability and evidence status                                                   |
| Owner default                 | Rate 50 or Seated posture applied only to absent fields, without rewriting source data         |
| MotionSequence                | Acceleration and optional gravity vectors; pairing establishes structure, not physical meaning |
| Structural vector             | Retained direction/calibration vector without an inferred physical transform                   |
| GPS slot                      | Original GPS sequence position, retained even without a usable typed fix                       |
| Diagnostic                    | Severity, stable code, JSON Pointer, message and optional original sample index                |
| JSON Pointer                  | RFC 6901 field location in the retained source                                                 |
| ImportSuccess / ImportFailure | Complete-import result; failure exposes no Recording                                           |
| DecodeSuccess                 | Valid supported source envelope; not a complete import or analysis result                      |
| Qt-independent                | Usable without constructing or importing Qt widgets                                            |
| Rider frame                   | Explicit rider coordinate frame whose physical mapping requires independent evidence           |
| Opaque video                  | H.264 MP4 output with a filled background                                                      |
| Alpha overlay                 | ProRes 4444 MOV output with transparency for compositing                                       |
| POV                           | Point-of-view ride footage aligned in external video-editing software                          |
| ADR                           | Architecture decision with rationale and evidence, retained in chapter 09                      |
| AnalysisProfile               | Immutable policy/configuration and explicit provisional permission                             |
| AnalysisResult                | Immutable explicit device/frame result retaining its complete import and provenance            |
| RecordingAnalysis             | Immutable shared snapshot of source, time and prepared analysis stages                         |
| AnalysisService               | Qt-independent current state, revisions and subscriptions                                      |
| ExportTimeline                | Bound analysis snapshot, source interval and deterministic video clock                         |
| SampleValues                  | Owned float64 bytes, validity mask and read-only NumPy views                                   |
| VERIFIED channel              | Verified only for its declared scope; raw-data verification does not qualify rider loading     |

`OrthonormalFrame` stores right-handed target axes as rows in DEVICE coordinates.
`RiderCalibration` binds an explicit provisional basis to a source hash; neither
type certifies real rider loading.
