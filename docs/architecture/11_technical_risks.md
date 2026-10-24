# 11. Risks and Technical Debt

[Architecture index](README.md)

| Risk                           | Current limit                                                                                | Handling                                                                          |
| ------------------------------ | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Physical sensor interpretation | Display-policy agreement does not qualify universal rider axes, units or sensations          | Preserve scoped evidence and provisional/unavailable states                       |
| Time and indices               | Acquisition epoch, source end-index convention and a common GPS/motion clock are unqualified | Preserve source indices/timestamps; do not infer alignment                        |
| GPS                            | Sentinels, accuracy and physical units are not universally qualified                         | Use approximate route context only; retain original values                        |
| Device differences             | Some recordings lack gravity/GPS; supplied arrays can be defective                           | Never reconstruct absent sensors or equate import success with analysis readiness |
| Schema evolution               | Only the documented Ride Forces and RFDB profiles are supported                              | Add adapters only with authorized source evidence                                 |
| Resource/filesystem behavior   | Budgets bound parsing, not total native RAM or all filesystem races                          | Retain bounded reads and explicit error states                                    |
| Native distribution            | CI does not cover every desktop/GPU or clean machine                                         | Keep platform baselines and verification limits explicit                          |
| Dependency security            | Passing compatibility tests is not a current vulnerability audit                             | Follow the [dependency policy](../development/DEPENDENCIES.md)                    |

## Scientific qualification

The adopted source-app projection/mean is separate from qualified physical rider
analysis. Manta has source-bound owner-confirmed display evidence; Kraken/Voltron
differences remain in the [source comparisons](../validation/APP_REFERENCE.md).
Other sources and settings retain their stated limitations.

Public Apple API definitions do not prove which quantities a Ride Forces exporter
stores. Gravity leaves yaw unresolved; direction vectors and riding-position
metadata do not establish mounting or pose. Rounded source axes are admissible
for the display policy but fail the strict frame API's exact-basis requirements.
Neither matching extrema nor source smoothing metadata proves private-algorithm
identity.

General physical qualification would require source/version identity, mounting
and pose references, controlled signed/stationary measurements, matched calibration
and smoothing, and verified clock relationships. It is deferred, not an automatic
release prerequisite. The [decisions](09_architecture_decisions.md#physical-qualification)
and [analysis concepts](08_concepts.md#scientific-provenance-and-gates) own these
gates. Original bytes and scientific evidence remain unchanged.

## Distribution limits

Windows packages are unsigned; macOS ad-hoc signing is not Developer ID signing
or notarization. Native CI is required for native packages, while Linux/macOS
clean-machine qualification remains open in the [roadmap](../ROADMAP.md).
The accepted FFmpeg delivery scope is maintained in
[release policy](../development/RELEASE.md#windows-packages).
