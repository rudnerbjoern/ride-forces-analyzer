# 9. Architecture Decisions

<!-- cspell:words orthogonalize -->

[Architecture index](README.md)

## Platform

Accepted: native Windows, Python/uv and PySide6 for offline processing of read-only
`.forces` files; sensor capture is out of scope. Domain/analysis stay outside Qt,
and frame generation stays separate from encoding. Pydantic validates settings;
Node supports development checks only. [Constraints](02_architecture_constraints.md)
and [Windows setup](../development/SETUP.md) own tool/version details. Python and
Node dependencies are reproducible through `uv.lock` and `package-lock.json`.

## Source ownership and import

Accepted and implemented: own original bytes, exact numeric tokens and an immutable
source tree alongside typed models; a mutable path or JSON re-encoding cannot
preserve evidence. Strict schema 2.2.0 / unversioned RFDB decoding, motion and optional validation
compose one deterministic, bounded Path/bytes service. Unknown fields and GPS stay
intact. Watch recordings disprove mandatory gravity/GPS; defaults apply only to
absence and never alter source. Expected input failures are structured outcomes;
caller misuse raises. [Import APIs](../development/IMPORT_SERVICE.md) and
[source concepts](08_concepts.md#source-ownership-and-validation) own details.

## Physical qualification

Deferred: successful parsing, valid numerical transforms and plausible magnitudes
do not establish sensor units, mounting/pose, gravity compensation, epoch or yaw.
Apple API field definitions are not a version-matched Ride Forces exporter mapping.
Keep raw access and per-channel unavailable/provisional states; require source-bound
unit/frame references and controlled signed/calibration/time comparisons before
claiming physical rider loading. Missing Watch sensors cannot be reconstructed
from other recordings. GPS remains coarse context, not measured speed or sync.
The adopted display policy below is separate from universal physical qualification;
[risks](11_technical_risks.md) retain the open evidence gates.

## Analysis models and libraries

Implemented APIs retain complete import/source identity, immutable buffers,
validity masks and calculation/configuration provenance. Raw inspection has no
NumPy dependency. NumPy handles arrays, Pint explicit declared-unit conversion,
SciPy passive rotations and Pandas an optional table adapter; upstream library
types stay behind typed interfaces. Bare Pint `g` means gram, not gravity:
use explicit `standard_gravity` where declared (`g0 = 9.80665 m/s²`). No gravity
addition/subtraction or sensor scaling is inferred. GeographicLib/AHRS/pyproj are
not adopted. [Analysis APIs](../development/ANALYSIS_MODELS.md) own contracts;
[third-party notices](../../THIRD_PARTY_NOTICES.md) own binary-license duties.

## Passive frame transforms

Implemented numerical convention: right-handed orthonormal target axes are rows
in DEVICE coordinates, with passive `v_target = R @ v_device` and inverse
transpose. Synthetic RIDER axes are forward/left/up, not an exporter mapping.
Admit orthogonality/determinant +1 with absolute tolerance `1e-10`, relative zero;
reject reflected/skewed bases without normalization or repair before calling SciPy
with `assume_valid=True`. Synthetic tests use `1e-14`, not an empirical accuracy
claim. Explicit source/unit/calibration/profile opt-in can produce PROVISIONAL
rider vectors only; no current original has qualified physical rider calibration.
Directly ordered source rows fail this strict admission for all five recordings.
The [frame API](../development/ANALYSIS_MODELS.md) owns missingness/overflow rules.

## Source-app projection

Adopted and implemented separately from strict frames: independently normalize
rounded source direction rows, require positive determinant and maximum absolute
Gram defect `<=0.003`, then dot-project acceleration directly as source-app g.
The bound allows three-decimal component rounding (`<=0.0005`), not physical
calibration error. Manta's row norms span 0.99974297–1.00024697, Gram defect is
0.000703 and determinant 0.9998744: rejecting them as exact rotations would discard
usable app-reference directions. Do not orthogonalize, replace axes or add gravity.

Use an odd centered mean of 1–51 samples, default 11; shorten/renormalize recording
edges and always recompute from unfiltered projection. Enable calibrated display
for every usable import, with raw fallback on preparation failure, without a
filename/hash allowlist. Manta at the pinned hash/window 11 has owner-confirmed
signs, g scale, mean, replay origin, Combined norm and gravity-to-vertical tilt;
other sources/windows remain provisional. Corpus extrema agree within 0.0002,
not a physical accuracy or private-algorithm identity guarantee. The
[source comparisons](../validation/APP_REFERENCE.md) preserve exact readouts and
Kraken/Voltron discrepancies; [concepts](08_concepts.md) and
[explorer contracts](../implementation/RAW_EXPLORER.md) define live behavior.

Combined is prepared alongside smoothing from the norm of the centered-mean
device x/y/z axes, using the same full-history window and shortened recording
edges. Rounded direction rows do not form an exact orthonormal basis, so the norm
of projected channels is not substituted. Combined shares the smoothing stage's
availability and provisional g interpretation; it does not qualify physical units.

## Export and remaining scope

Implemented outputs are transparent ProRes 4444 MOV and independent opaque H.264
MP4, with manual video alignment. Preview and encoding share production frames;
CPU fallback remains available. Interactive sample playback is implemented separately
from export. Additional outputs, POV synchronization and standalone packaging
remain planned in the
[roadmap](../ROADMAP.md); [export contracts](../implementation/VIDEO_EXPORT.md)
and [deployment limits](07_deployment_view.md) define the current boundary.
