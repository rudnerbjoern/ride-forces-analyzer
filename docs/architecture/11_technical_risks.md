# 11. Risks and Technical Debt

[Architecture index](README.md)

| Risk / debt                      | Known state                                                                                                                       | Consequence / next evidence gate                                                                                                |
| :------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------ |
| Unverified motion semantics      | General physical source/frame qualification remains open; app-reference signs/scale have scoped evidence                          | Retain scoped app-reference evidence; universal physical qualification is deferred                                              |
| Unverified time / indices        | Epoch, end-index convention and a common motion/GPS clock are unresolved                                                          | Preserve indices/timestamps; no inferred synchronization or chronology claim                                                    |
| GPS interpretation               | Negative speed/course/accuracy and suspicious values are preserved with warnings                                                  | Units, sentinels and physical plausibility require independent evidence                                                         |
| Device capability differences    | Apple Watch can lack gravity/GPS; present arrays can still be defective                                                           | Never synthesize missing sensors; separate import success from analysis readiness                                               |
| Schema evolution                 | Only 2.2.0 is supported; observed fixtures are not a manufacturer specification                                                   | Obtain authorized evidence and explicit adapters/tests before accepting another version                                         |
| Resource / filesystem guarantees | Shape/diagnostic budgets are implemented; total RAM, cold-cache and hostile filesystem/ACL behavior are not fully verified        | Retain conservative limits and document benchmark/mock boundaries                                                               |
| GUI and service integration      | Raw explorer opens files and shows source curves; persistent library/playback are planned                                         | Retain implemented interactive import; complete library/playback acceptance separately                                          |
| Export and release compatibility | ProRes/H.264 encode and Resolve import have scoped evidence; Onride compositing, synchronization and clean-VM release remain open | Retain codec evidence and verify remaining M6–M8 boundaries                                                                     |
| Dependency security              | Node tooling includes parser risks; current advisory status requires a fresh audit                                                | Retain reviewed overrides; follow the [dependency policy](../development/DEPENDENCIES.md#node-overrides-and-security-boundary)  |

M2 parsing/integrity acceptance does not establish sensor accuracy, Ride Forces
algorithm equivalence or suitability for safety-critical interpretation. Resolve
scientific questions through the [analysis concepts](08_concepts.md#scientific-provenance-and-gates)
without changing original source evidence. M2 limitations and scoped verification
boundaries remain in the [import contract](08_concepts.md#source-ownership-and-validation).

## Unresolved scientific qualification

Native Linux/macOS package checks do not establish compatibility with every
distribution, desktop, GPU or a clean machine. macOS ad-hoc signatures are not
Developer ID signing/notarization. A release requires the native package jobs
for all prepared targets; Windows-only mocks/static checks cannot replace them.
These distribution limits are independent of the scientific gates below.

[physical qualification boundary](09_architecture_decisions.md#physical-qualification) links
actual M2/fixture observations to proposed channel gates. Owner acceptance of
that policy and independent scientific qualification remain open:

- Public Ride Forces/Apple guidance does not bind export fields to API quantities,
  signs or units. No generic gravity compensation or automatic SI conversion is qualified; the source-app projection decision
  defines the separate adopted app-reference g display.
- Gravity leaves yaw unresolved. The six source vectors, device label and Seated
  default do not prove a rider frame; Manta's Flying pose and Watch wrist motion
  need separate mounting/calibration references.
- Source extrema and smoothingFactor=1 do not identify the source algorithm,
  endIndex inclusion or private algorithm identity. Manta/Kraken/Voltron comparisons
  exist with the known differences retained in the comparison report.
- Increasing GPS numbers do not establish seconds, epoch, datum or motion offset.
  Negative-value semantics remain field-specific hypotheses; raw values survive
  any future optional-product exclusion.
- All originals are eligible for raw inspection, with units/axes UNKNOWN.
  Definitive rider outputs and app equivalence remain unavailable; Iron Gwazi
  additionally lacks GPS/gravity. Assumption-based exploratory output requires
  explicit opt-in and PROVISIONAL labeling. Device analysis enforces source-specific
  unit/quantity contract gates; caller references do not certify source semantics.

Qualification requires source-hash-linked app/version, device mount and rider pose,
controlled signed/stationary references, matched graph/calibration/smoothing settings
and independently verified epoch/clock offsets. Public
[Core Motion](https://developer.apple.com/documentation/coremotion/cmdevicemotion)
and [Core Location](https://developer.apple.com/documentation/corelocation/cllocation)
definitions do not prove which API quantities the exporter stores. These open
physical gates are separate from reduced-M3 product acceptance.

Frame analysis supplies validated numerical transforms and a PROVISIONAL-only rider gate,
not empirical calibration. The directly ordered source direction vectors fail its
strict numerical admission policy; they must not be silently normalized into a
physical frame. Qualification still needs versioned axis/mount/pose references.
See [passive frame decision](09_architecture_decisions.md#passive-frame-transforms).

Manta now has owner-supplied app screenshots and a source-bound confirmed
app reference (the source-app projection decision). The owner accepted direction projection, g scale, signs,
11-sample mean, replay origin, Combined and Orientation contracts. Source rounding
is retained; other recordings now use the same owner-adopted display policy by default when
usable directions are present. Independent qualification remains separate.

Unresolved physical mounting/epoch/private-algorithm questions remain limitations,
not automatic reduced-M3 blockers. Current acceptance uses adopted source-app
projection/mean and documented discrepancies. GPS cannot be promoted from rough
spatial reference to force/speed measurement. Reduced M3 is complete with extrema and focused Windows evidence; broader
physical research and full-suite execution remain outside the current acceptance scope.
