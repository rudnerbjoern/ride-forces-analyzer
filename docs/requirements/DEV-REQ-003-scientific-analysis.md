# DEV-REQ-003 — Force preparation and basic extrema

<!-- cspell:words Butterworth -->

**Milestone:** M3 · **Status:** Complete within the owner-approved reduced scope;
[focused Windows acceptance](../validation/M3.md).
**Purpose:** Reliable preparation of imported Ride Forces channels for the explorer,
subsequent replay and video overlays. This is not a general scientific analysis platform.
**Input:** Verified M2 ImportSuccess and all five [authorized originals](../development/RECORDINGS.md).
**Architecture:** The twelve [arc42 chapters](../architecture/README.md) remain authoritative.
**Plan/evidence:** [Implementation plan](../implementation/DEV-REQ-003/PLAN.md),
[source-app comparisons](../validation/APP_REFERENCE.md),
[explorer validation](../validation/RAW_EXPLORER.md).

## 1. Required product behavior

- **SCI-001 Input:** Consume the immutable complete M2 result; never reparse JSON
  in analysis or widgets, rewrite sources or invent absent sensors/directions.
- **SCI-002 Provenance:** Retain source hash, algorithm, window, calculation time,
  source/default sample rate, channel meaning/unit and per-source evidence status.
- **SCI-003 Frames:** Use the source-app direction projection in ADR 0006 for the
  product. Keep the stricter generic frame API independent; it makes no universal
  physical rider-calibration claim.
- **SCI-004–006 Quantities:** Preserve raw unknown-unit channels. App-reference g
  uses the adopted source policy, without adding/subtracting gravity. Existing
  device-vector norms and Pint conversion retain their explicit source-bound gates.
- **SCI-007–009 Directions:** Independently normalize rounded source directions
  only under ADR 0006 admission; reject degenerate/malformed bases with raw fallback.
  Positive lateral means right, negative left; positive longitudinal acceleration,
  negative braking. Do not infer yaw, mounting or physical orientation from gravity alone.
- **SCI-010–012 Preservation:** Keep source units/epochs/sentinels, source extrema
  and missing data intact. Computed products are separate artifacts. Unknowns and
  unsupported capabilities stay explicit; no zero filling or source repair.

## 2. Time and smoothing

- **SIG-001:** Keep index/rate time INFERRED_UNIFORM; integer-rate replay uses
  start-relative MM:SS.ff, ff a sample counter. GPS never controls sensor time.
- **SIG-002:** Retain raw channels and unfiltered calibrated projections separately.
- **SIG-005:** Use the implemented centered arithmetic mean with odd windows 1–51,
  default 11, shortened/renormalized recording edges. One disables smoothing.
  Always recompute from unfiltered projection. No added filter family is required.
- **SIG-008:** Retain source-rate limitations; no extra physical precision or new
  samples are implied. Smoothing may suppress short peaks.
- Live slider updates, right-click default reset, raw toggle and reopen behavior
  follow the [explorer contracts](../implementation/RAW_EXPLORER.md).

## 3. Basic extrema — implemented

- **SIG-006:** Return minimum/maximum for each of the three active displayed channels
  over the inclusive selected sample interval. Use all available samples in that
  interval and the selected raw or calibrated smoothing mode, without a second
  selection-edge filtering pass. Chart visibility does not suppress a channel result.
- **SIG-009:** Include interval endpoints/sample count, each extremum's value,
  original sample index and recording-relative time. Replay labels use the existing
  presentation formatter. If multiple samples tie, return the earliest source index.
- Reject invalid/out-of-range/reversed intervals. A one-sample interval has equal
  minimum and maximum. Preserve negative, positive and zero values exactly as the
  chosen channel representation permits; do not substitute source minForce/maxForce.
- **SIG-010:** Retain source identity, raw/calibrated mode, unit and smoothing window
  so results cannot be reused for another source or setting. Raw extrema do not claim g.
  Empty/unavailable channels return an explicit unavailable result or documented
  validation error, never fabricated extrema.

## 4. Dependencies and output boundaries

- **LIB-001–003:** Reuse locked NumPy, existing SciPy frame math and Pint boundaries.
  No new dependency is required for projection, mean or basic extrema. SciPy signal
  processing/interpolation is not required for this milestone.
- **LIB-005/008:** Pandas stays optional; retain locked installation, license and
  compatibility rules. Installed libraries alone establish no feature requirement.
- **RES-001–002/004–005:** Keep typed immutable results with provenance/capability,
  independent of Qt/storage/playback/rendering. Presentation formatting lives outside
  numeric calculations; widgets contain no analysis/validation logic. Recompute from
  retained data when configuration changes; never rewrite an original recording.
- Existing generic device/frame models remain supported and tested; no unrelated
  API/dependency removal is part of reducing this scope.

## 5. Explicitly outside current M3 acceptance

| Requirement area                                               | Current disposition                                                                      |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| LIB-004/006/007, GPS geodesics/speed/altitude/quality profiles | Not required; no GeographicLib/AHRS/pyproj adoption                                      |
| GPS-001–010, VAL-005 analytical GPS engine                     | Not required; preserved import and existing coarse overview remain independent           |
| SIG-003–004 Butterworth SOS/zero-phase filtering               | Deferred; current configurable mean is sufficient                                        |
| SIG-006 events/threshold durations beyond extrema              | Deferred; no automatic event or safety classification                                    |
| SIG-007 interpolation                                          | Deferred to an explicit playback requirement                                             |
| SIG-009 mean/RMS/quantiles beyond basic extrema                | Deferred; no general statistics engine                                                   |
| RES-003 general scientific/GPS profiles                        | No new profiles required; existing profiles remain supported                             |
| Universal physical rider/sensor calibration                    | Not required for closure; capability limits and source-app evidence must remain explicit |
| Full analysis performance/memory research                      | Not required; representative responsiveness is sufficient                                |

These exclusions are accepted scope boundaries, not verified implementations.
GPS remains a rough spatial reference under the owner's product decision, not a
future M3 force/speed measurement requirement. Later additions need a concrete
use case and explicit authorization. Combined/Orientation remain evidence-only.

## 6. Validation and acceptance

- **VAL-001–004:** Reuse and extend meaningful analytic projection, sign, strict
  frame/unit and centered-mean regressions; verify all allowed windows, edges,
  constants/impulses and source immutability. No Butterworth or geodesic suite required.
- **VAL-006–008:** All five originals retain exact bytes/hash and missing sensor
  behavior. Keep independent Manta references, Kraken start mismatch and Voltron
  maximum-display difference visible; exact private algorithm equivalence is not
  required. Synthetic tolerances are distinct from rounded app comparisons.
- **VAL-009:** Under the owner's current focused-test instruction, complete affected
  native Windows checks and reuse only valid unchanged evidence. Do not run full
  suites without renewed approval or claim a fresh full-suite pass. Retain a compact final
  `docs/validation/M3.md` report before declaring M3 complete. Local acceptance
  does not authorize Git delivery; follow AGENTS.md.
- **VAL-010:** Check responsive loading/navigation and extrema/smoothing updates
  on the five representative recordings. No universal timing/RAM claim or separate
  benchmark platform is required.

| Criterion | Required evidence for reduced M3                                                                      |
| --------- | ----------------------------------------------------------------------------------------------------- |
| AC-01     | Adopted source-app policy, signs/time, raw fallback and explicit physical-calibration exclusions      |
| AC-02     | Existing locked NumPy/SciPy/Pint compatibility; no new library requirement                            |
| AC-03     | Immutable raw/calculated results with source/configuration provenance                                 |
| AC-04     | Analytic norms/projections/rotations and directional signs; no universal physical qualification claim |
| AC-05     | Existing centered-mean windows/edges, raw preservation and repeatable switching                       |
| AC-06     | Basic extrema for all three channels and inclusive selections, deterministic ties and units           |
| AC-07     | GPS stays reference-only and independent; absent GPS/gravity remains absent                           |
| AC-08     | Existing source comparisons and known discrepancies accurately documented                             |
| AC-09     | Original bytes retained; offline processing; analysis outside widgets                                 |
| AC-10     | Owner-authorized focused Windows verification, responsive use, final report and aligned architecture  |

The criteria above define current acceptance; older stage reports only evidence
their tested code/contracts and do not automatically satisfy the reduced criteria.
**ARC-001–004:** Maintain only the twelve arc42 views, link ADRs from chapter 09,
mark implemented/planned/unverified behavior and check changed diagrams/docs.
Current criteria are verified in the focused acceptance report; broader excluded
research is not a completion blocker.
