# Editable ride markers and calibration

**Status: typed overrides, reference validation/provenance, basis construction and
partial recalculation through the service, hash-bound persistence, import restoration
and bound export/job recipes, chart-menu actions and automatic saving/reset for all
four markers are implemented. Final cross-feature validation remains planned.**
This is an empirical reconstruction of reference calibration, cross-checked against
the five original recordings' stored axes. General equivalence to the Ride Forces
app algorithm and physical rider calibration remain unqualified. Existing
[source-app projection](../architecture/09_architecture_decisions.md#source-app-projection)
and [source evidence](../validation/APP_REFERENCE.md) remain separate contracts.

## Interaction and persistence

- Chart right-click: set Start, End, Gravity and Incline; separator; reset each
  to its original value; separator; reset all. Use localized labels and the
  nearest sample at the clicked position under the current zoom. No separate dialog.
- Changes apply and save automatically, keyed by original-file SHA-256, independent
  of path. Reopening restores all four choices. Source bytes, source markers,
  stored direction vectors and unknown fields remain unchanged.
- Start/end remain ordered inclusive indices. Gravity/incline only require a valid
  original sample index; they may lie outside the ride interval or precede each other.
- Individual reset preserves other choices. An absent original Gravity/Incline
  becomes absent again. Reset all restores the original source calibration and
  removes local overrides.

## Reference calibration rule

1. Read acceleration from the complete original device-axis sequence. For each
   selected calibration sample, use a fixed centered 5-sample arithmetic mean
   (index -2 through index +2), shortened and renormalized at recording edges.
   This reference window is independent of the user's force-smoothing setting.
   Do not substitute gravity samples or acceleration minus gravity. At the original
   indices, this method reproduces all 45 stored direction components across the
   five fixtures when rounded to source precision; see
   [reference-calibration evidence](../validation/APP_REFERENCE.md#reference-calibration-evidence).
2. A custom Gravity reference defines the unit vertical axis from its mean vector.
   The user must choose a steady reference with normal positive seat loading.
   Without a custom Gravity choice, retain the original source vertical direction.
3. A custom Incline reference defines the longitudinal candidate from its mean
   vector after removing the component along the effective vertical axis.
   Normalize it and choose its sign to agree with the original longitudinal
   direction. Without a custom Incline choice, use the original longitudinal
   direction projected onto that same plane.
4. Derive the lateral axis from longitudinal cross vertical. Use the resulting
   orthonormal, right-handed basis for direct acceleration projection. Do not add
   or subtract gravity, rescale force units or reinterpret missing sensor data.
5. Tilt remains the angle between each available gravity sample and the effective
   vertical axis. Changing Incline alone does not change tilt. Missing gravity
   keeps orientation unavailable; it does not prevent acceleration-based references.
6. With neither calibration override active, use the exact original stored
   direction vectors and existing source-app projection policy. Do not replace
   the rounded source basis with the reconstructed calibration basis on reset.

Zero/non-finite means, near-parallel reference directions, missing source axes or
ambiguous longitudinal polarity must produce an explicit diagnostic, not guessed
axes. Reference admission uses dimensionless tolerances of `1e-6` for the sine
between references and absolute cosine against the longitudinal polarity anchor;
these are numerical limits, not sensor-accuracy or physical thresholds. Invalid choices
must not replace saved valid references. No suitability for arbitrary sensor
mounts, rider poses, airtime sensations or safety assessment is established.

## Partial recalculation through the existing service

| Change          | Recalculate                                                            | Reuse                                        |
| --------------- | ---------------------------------------------------------------------- | -------------------------------------------- |
| Start / End     | Effective markers and replay/view/export times                         | All numerical stages and original samples    |
| Gravity         | Reference basis, projection, smoothing, context/events and orientation | Original import and raw sample buffers       |
| Incline         | Reference basis, projection, smoothing and context/events              | Original import, raw buffers and orientation |
| Force smoothing | Smoothing and configured dependent context/events                      | Reference basis, projection and orientation  |

Use the existing `AnalysisService`, dependency invalidation and worker/UI adapter;
do not add a parallel calculation path. Preserve initial delivery, revision guards,
failure completion and retained previous snapshots. Rapid requests adopt the latest
choice. Exports/previews/batches bind the effective references and algorithm version;
later edits do not change an already bound export or saved job.

## Short implementation steps

1. Add typed Gravity/Incline overrides, reference-calibration provenance and finite/degeneracy validation.
2. Implement the reference basis and extend existing service dependencies for partial recalculation.
3. Extend hash-bound local storage, import restoration and bound export/job serialization; retain original evidence.
4. Extend the chart menu and automatic saving/reset behavior for all four markers.
5. Test synthetic axes/polarity, invalid references, stage reuse, persistence, UI and exports; cross-check all authorized recordings and update maintained contracts.
