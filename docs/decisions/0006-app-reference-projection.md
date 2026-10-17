# ADR 0006 — Source-bound app-reference projection

<!-- cspell:words orthogonalization nonorthogonal -->

**Status:** Implemented. The owner confirms the Manta source-app contracts
(2026-10-17) and adopts the display policy for all usable imports. Independent
Manta verification remains scoped to its pinned source and default window 11;
other sources/windows retain PROVISIONAL evidence. Full M3 acceptance is separate.

## Decision and rationale

Stored rounded source directions are not exact rotation matrices. Manta's
vertical/lateral/longitudinal row norms are 0.99988499/0.99974297/1.00024697,
maximum Gram defect 0.000703 and determinant 0.9998744. They fail the strict
[ADR 0005](0005-passive-frame-transforms.md) frame admission without being corrupt.

For this separate operation, normalize each row independently and dot-project
source acceleration directly as source-app g. Require positive determinant and
maximum absolute Gram defect <=0.003, covering three-decimal rounding (component
error <=0.0005). This is a numerical admission bound, not calibration accuracy.
No orthogonalization, cross-product replacement, rotation repair or gravity
addition/subtraction is permitted. Slightly nonorthogonal rows remain possible;
this operation is not OrthonormalFrame/RiderCalibration.

Apply a centered arithmetic mean with configurable odd window 1–51, opening
default 11. One returns unfiltered projection. Recording-edge windows shorten
and renormalize; this is project behavior, not verified private source-app edge
behavior. Never cascade filtering or rewrite source smoothingFactor.
Default 11 reproduces Manta stored vertical extrema within 0.000010 source units
and all five originals within 0.0002. Quantization prevents bitwise equality;
the cross-check does not uniquely identify the private algorithm.

## API and feature availability

`analysis.reference.AppReference` / `reconstruct_app_reference` retains source
hash, calculation time, algorithm/window, raw/filtered channels, library version,
capability and confirmed-contract references. Output is Vertical/Lateral/Longitudinal.
Changing the window updates provenance from the retained unfiltered projection.
Signs follow stored rows: lateral positive right/negative left, longitudinal
positive acceleration/negative braking. Strict scientific frame/unit APIs are
unchanged and require their own evidence.

Calibrated forces defaults on for every usable import, without filename/UUID/hash
allowlists. Missing/invalid directions or unavailable numerical support produce
CALIBRATION_UNAVAILABLE diagnostics and preserve raw import. Short nonempty
recordings use available mean neighbors. Failed parsing retains the previous view.
NumPy is a locked analysis extra; raw startup does not require its availability.
Time, local selection, GPS and original bytes are independent of this display policy.

## Confirmed evidence and limits

The owner's Manta confirmation covers g scale, normalized directions/signs,
11-sample mean, start-marker replay origin, Combined as the norm of filtered
components and Orientation as current-gravity-to-stored-vertical angle. Combined
and Orientation are comparison tests, not implemented UI products. Replay is
`MM:SS.ff` with sample counter at integer rate; the Kraken readouts disambiguate
this from hundredths. Internal time remains INFERRED_UNIFORM index/rate.

[Comparison evidence](../validation/APP_REFERENCE.md) retains the exact replay
rows, corpus extrema, weather/GPS observations and unresolved Kraken start/Voltron
vertical-maximum display differences. All Manta compared readouts match at shown
precision; this confirmation does not qualify arbitrary source hashes, physical
mounting, private algorithm identity, endIndex inclusion or GPS/sensor clocks.

The supplied source-app screenshots/readouts in the conversation are visual
references; they are not copied into the repository. Direction labels and
configurable smoothing are product behavior described by the
[explorer contracts](../implementation/RAW_EXPLORER.md). No new filter family or
dependency is introduced; a uniform mean's configurable size does not establish
11 as a standard. [SciPy's uniform-filter definition](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.uniform_filter1d.html)
describes the general operation, not the source app or this edge policy.

## Product scope

This policy and existing centered mean are the force-preparation basis of reduced
M3. Basic selected-range extrema and final Windows acceptance remain required.
No additional filter, general physical calibration, event classification or GPS
measurement is required to close that scope. These exclusions do not change
per-source evidence status, strict generic frame gates or known discrepancies.
