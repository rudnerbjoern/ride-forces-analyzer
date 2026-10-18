# ADR 0004 — Analysis contracts and scientific library policy

Status: Proposed policy with implemented model/device/frame contracts.
General physical qualification remains deferred.
[DEV-REQ-003](../requirements/DEV-REQ-003-scientific-analysis.md) defines the
accepted reduced-M3 boundary; [ADR 0003](0003-scientific-semantics-and-capability-gates.md)
is not approval of universal sensor semantics.

## Decision and rationale

Analysis consumes full immutable M2 ImportSuccess without re-decoding or replacing
source evidence. Public results retain source, profile, provenance, ordered
diagnostics, immutable channels and explicit capability/missingness.
Model construction validates structure; it does not perform calculations or
certify physical interpretation. The [API guide](../development/ANALYSIS_MODELS.md)
owns constructor, array-ownership and migration contracts.

Use NumPy for owned numerical buffers, Pint for explicit declared-unit conversion
and SciPy for passive rotations. Keep library-specific quantities/registries/
Rotation objects out of public result models. Raw inspection must not depend on
optional numerical packages.

| Library       | Current role                      | Boundary                                                     |
| ------------- | --------------------------------- | ------------------------------------------------------------ |
| NumPy         | Owned arrays and numeric kernels  | Source/quantity declarations remain explicit                 |
| Pint          | Device component conversion       | Bare g is rejected; standard_gravity means g0 = 9.80665 m/s² |
| SciPy         | Explicit passive frame transforms | No automatic basis repair or source qualification            |
| Pandas        | Optional table adapter            | Not an analysis-core requirement                             |
| GeographicLib | Not adopted                       | Analytical GPS is outside current product scope              |
| AHRS / pyproj | Research only                     | No approved sensor-fusion or coordinate-conversion use case  |

The five files lack a complete exported gyro/magnetometer sequence; this does not
prove the acquisition app never used such sensors. Installed libraries do not
authorize added filters, interpolation or geodesics. Those need concrete product
requirements.

Device APIs bind source hash, sequence, unit/quantity and evidence references.
A Pint scale factor precedes array calculations; neither gravity addition/
subtraction nor sensor compensation is inferred. Generic rider transforms require
explicit provisional calibration. Source-app projection/mean remains the separate
[ADR 0006](0006-app-reference-projection.md) contract.

## Compatibility and redistribution limits

Audited regular CPython 3.14.6 Windows AMD64 wheels:
NumPy 2.5.4, Pint 0.26.1, SciPy 1.18.1 and Pandas 3.0.6.
The 2026-10-14 compatibility audit used synthetic APIs, not real-source
qualification. Actual installed versions/hashes come from
[repository locks](../validation/DEPENDENCIES.md); no package table here overrides them.
ARM64, free-threaded Python, source builds and clean-VM installation are unverified.

Top-level NumPy/SciPy/Pint/Pandas licenses are BSD-3-Clause, but actual binary
notices include additional NumPy licenses and OpenBLAS/LAPACK/GCC components,
including GPL-3.0-or-later WITH GCC-exception-3.1. Retain complete notices.
Pint's actual text is three-clause BSD; GeographicLib's evaluated text is MIT.
Standalone M8 redistribution requires review of assembled binary/transitive
licenses, not blanket clearance from this ADR.

The dated PyPI metadata check listed no vulnerabilities for its audited candidates;
it was not a complete native/transitive security audit. Recheck before release.

## Consequences

Results can be reproduced and restricted independently per channel without losing
original data. Immutable buffers protect normal Python/NumPy use, not malicious
native pointer writes. References are caller attestations; valid structure,
VERIFIED raw handling and synthetic success do not certify rider loading.
[M3 acceptance](../validation/M3.md) scopes integrated verification.

## Primary references

- [NumPy ownership flags](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.setflags.html)
  and [license](https://numpy.org/doc/stable/license.html).
- [SciPy 1.18.1 metadata](https://pypi.org/project/scipy/1.18.1/)
  and [license](https://github.com/scipy/scipy/blob/v1.18.1/LICENSE.txt).
- [Pint conversion](https://pint.readthedocs.io/en/stable/user/numpy.html)
  and [license](https://github.com/hgrecco/pint/blob/0.26.1/LICENSE).
- [GeographicLib](https://geographiclib.sourceforge.io/Python/doc/),
  [AHRS](https://pypi.org/project/AHRS/0.4.0/) and
  [pyproj](https://pypi.org/project/pyproj/3.8.0/) for deferred evaluation only.
