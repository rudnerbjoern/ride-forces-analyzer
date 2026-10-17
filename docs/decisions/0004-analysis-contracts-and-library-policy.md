# ADR 0004 — Analysis contracts and scientific library policy

Status: Proposed for owner review, 2026-10-14. Stage 1 model contracts are
implemented and tested. Device primitives with Pint, strict SciPy frame transforms and the separate
source-app projection/mean are implemented. General scientific qualification,
broad statistics and GeographicLib adoption are not required by reduced M3. [ADR 0003](0003-scientific-semantics-and-capability-gates.md)
is deferred research; no physical source-unit or rider-frame uncertainty is resolved here.

Requirements: [DEV-REQ-003](../requirements/DEV-REQ-003-scientific-analysis.md),
LIB-001–008, SCI-001–003, RES-001–005 and ARC-001–004. AC-02/AC-03 are only
partially evidenced: isolated library compatibility and model contracts are not
project integration or a complete calculation service.

## Verified M2 prerequisite

The unchanged public `import_forces` and `import_forces_bytes` APIs were reconfirmed
on native Windows Python 3.14.6 before coding: **61 tests passed in 14.42 s** across
`tests/test_import_service.py` and `tests/test_project.py`. They preserve all five
original recordings, source number/string types and source/default metadata.
Only full ImportSuccess is accepted by AnalysisResult; decoder/subset success and
ImportFailure are rejected. Original M2 objects and their diagnostics remain owned
by the result, without re-decoding, replacing bytes or inserting scientific units.

## Library and lock audit

Release metadata, published wheels and installed license files were inspected on
2026-10-14. The target tested is regular CPython 3.14.6, Windows AMD64; ARM64,
free-threaded Python, clean-VM installation and source builds are unverified.

| Library       | Audited version | Top-level license | Python requirement | Project lock / installation | Native evidence                                                 |
| ------------- | --------------- | ----------------- | ------------------ | --------------------------- | --------------------------------------------------------------- |
| NumPy         | 2.5.4           | BSD-3-Clause      | >=3.12             | Already locked/installed    | cp314 Windows AMD64 wheel; immutable-buffer smoke               |
| SciPy         | 1.18.1          | BSD-3-Clause      | >=3.12             | Adopted for passive frames  | cp314 Windows AMD64 wheel; rotation/filter/interpolation smokes |
| Pint          | 0.26.1          | BSD-3-Clause      | >=3.12             | Adopted in Stage 2          | Universal wheel; conversion/dimensionality smoke                |
| GeographicLib | 2.1             | MIT               | >=3.7              | Absent; proposed adoption   | Universal wheel; synthetic WGS84 inverse smoke                  |
| Pandas        | 3.0.6           | BSD-3-Clause      | >=3.11             | Already locked/installed    | cp314 Windows AMD64 wheel; optional table smoke                 |
| AHRS          | 0.4.0           | MIT               | >=3.9              | Absent; research only       | Metadata/universal wheel only; no runtime test                  |
| pyproj        | 3.8.0           | MIT               | >=3.12             | Absent; research only       | Metadata/cp314 wheel only; no runtime test                      |

Versions are exact audited release candidates, not a new project pin policy.
SciPy declares `numpy>=2.0.0,<2.8`; existing NumPy 2.5.4 satisfies it. Pandas on
Python 3.14 requires NumPy >=2.3.3. Only base candidate packages were installed:
upstream documentation/test extras and their unrelated dependencies were excluded.

The isolated `.tmp/m3-stage1-audit/` environment pinned the candidates on
Python 3.14.6 (13-package audit lock, 12 installed distributions); eight synthetic
integration checks passed. This proves compatibility in that audit scope, not
adoption of every candidate or real-source physical qualification. Current root
adoption is NumPy/Pint/SciPy; [locked inventory](../validation/DEPENDENCIES.md)
reflects the actual project environment. GeographicLib is not required for the current GPS reference-only product.

### License and security scope

NumPy metadata declares `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`.
The actual NumPy and SciPy Windows wheel notices additionally identify OpenBLAS,
LAPACK and GCC runtime components, including
`GPL-3.0-or-later WITH GCC-exception-3.1`. Retain the complete distributed license
files and notices; a top-level BSD label alone is not the binary license inventory.
Pint's actual license text is three-clause BSD despite its abbreviated PyPI label.
GeographicLib's actual license is MIT. Transitive audit notices include BSD,
MIT, PSF and Apache/public-domain material. Standalone M8 redistribution must
review the actual assembled binary notices; this is no blanket release clearance.

PyPI returned no listed vulnerabilities for the four audited candidate versions.
That is a dated metadata observation, not a complete vulnerability scan of native
bundles, every transitive package or the repository. Existing security follow-up
is unchanged. Recheck advisories and distribution notices before dependency
adoption/release; no alert or quality rule was suppressed.

### Roles and deferred libraries

Use existing NumPy for the model's immutable array boundary and future finite
numeric kernels. SciPy implements passive rotations and remains the proposed worker for
offline SOS filtering and interpolation. Pint implements the Stage 2 dimensional
boundary only with independently qualified source units. GeographicLib remains
the proposed declared-WGS84 horizontal geometry implementation.
Do not replace those roles with bespoke numerical algorithms.

Pandas remains an optional tabular adapter, not an analysis-core requirement.
AHRS is research only: the five files contain no complete raw gyroscope/
magnetometer sequences and do not qualify a new full sensor-fusion pipeline.
This does not mean the source app did not use those sensors during acquisition.
pyproj is research only until an approved coordinate-system conversion need exists;
it does not replace GeographicLib for the initial WGS84 policy. Neither was installed.

## Model boundary decisions

Implemented in [analysis.models](../../src/ride_forces_analyzer/analysis/models.py)
and exported from `ride_forces_analyzer.analysis`; the
[model guide](../development/ANALYSIS_MODELS.md) gives concrete contracts and tests.
Model construction performs no calculation. Device norms/unit conversion and
strict provisional frame math are implemented. ADR 0006 defines the separate
source-app projection/mean consumed by the explorer; geodesics and storage remain planned.

- AnalysisResult retains full M2 ImportSuccess, profile, provenance, ordered
  diagnostics and immutable channels. Source schema/bytes/GPS/import diagnostics
  remain available through the retained source. Nonempty unique channels and
  independently bounded acceleration/gravity/GPS indices are checked.
- AnalysisProfile defaults to raw_device_only. Scalar configuration is copied
  into a sorted read-only mapping; evidence/assumption collections become tuples.
  Additional profiles require policy references; provisional results require
  explicit permission and named assumptions. These references are caller
  attestations, not an approval database or proof that evidence is sufficient.
- Quantity, canonical unit, frame, capability, source sequence, processing and
  time labels are enums. Physical values require compatible assigned units;
  VERIFIED physical values cannot use ASSUMED unit evidence. Raw source values
  retain UNKNOWN units and cannot claim rider/world frames. Missing capabilities
  use no samples and an explicit reason; invalid and unavailable remain distinct.
- SampleValues snapshots numeric arrays into owned little-endian float64 bytes.
  Every accessor creates a fresh read-only NumPy view backed by those bytes.
  Caller aliases, mutable ndarray metadata and WRITEABLE toggling cannot alter
  the retained contract. Explicit missing rows contain NaN with a false validity
  flag; valid zero is a finite value, not absence. Infinities/boolean/object/
  complex arrays and inconsistent masks are rejected. Original source precision
  remains in M2; float64 accessors are not lossless replacements for source tokens.
- TimeBasis keeps M2 SampleRate and its origin for INFERRED_UNIFORM, assigns no
  epoch to unverified/inferred time and requires references for verified seconds.
  It carries no generated timeline or source date conversion. Calculation time
  is explicit timezone-aware UTC and separate from recording timestamps.
- AnalysisProvenance binds the complete M2 provenance, engine version, algorithm
  and calculation timestamp. Profile/schema/configuration and per-channel unit,
  frame, time, raw/filtered and evidence labels complete the result provenance.
  Changed algorithms/policies require a newly identified result from retained M2
  data, never alteration of an original or silent reuse of a previous result schema.

NumPy interoperability is intentionally limited to SampleValues input/output,
as required by Stage 1. SciPy Rotation objects, Pint registries/quantities and
GeographicLib dictionaries are not public model types. Frozen containers and
buffer ownership protect normal Python/NumPy use; malicious native pointer writes
or deliberate bypass of frozen dataclasses are outside that guarantee.

## Acceptance boundary

Model validation enforces structural contracts, not source-app truth. VERIFIED
raw values mean typed source-data handling, not verified rider loading. Result
validity is VALID/RESTRICTED/INVALID for the supplied contract and channel states;
it is not certification of physical interpretation. The proposed gates in ADR 0003
still require independent evidence and owner review before a definitive rider result.
Current originals remain unit/frame/time-unqualified; Iron Gwazi still has no
GPS/gravity. No synthetic smoke/reference is presented as evidence for their units.

Stage 2 was subsequently instructed explicitly for NumPy norms and Pint conversion,
including the necessary Pint analysis-extra/lock adoption. Pint 0.26.1 and its
transitive dependencies are now root-locked; other candidate adoption and general
scientific-policy approval remain open.

The device API uses a closed acceleration-unit enum, separate source/quantity
references and source-hash/sequence binding. One Pint SI factor is computed per
channel, followed by NumPy array multiplication and stable Euclidean norms.
Bare `g` is rejected: Pint treats it as gram; `standard_gravity` converts explicitly
using g0 = 9.80665 m/s². No load-factor or sensor compensation calculation is added.
Synthetic references qualify their synthetic source only; all real units remain
unknown. Public types expose no Pint registry/quantity. See the
[implemented device API](../development/ANALYSIS_MODELS.md#device-only-vectors-and-units--stage-2)
and [Pint conversion documentation](https://pint.readthedocs.io/en/stable/user/numpy.html).

## Primary references

- [NumPy 2.5.4 release metadata](https://pypi.org/project/numpy/2.5.4/) and [license](https://numpy.org/doc/stable/license.html)
- [SciPy 1.18.1 release metadata](https://pypi.org/project/scipy/1.18.1/) and [license](https://github.com/scipy/scipy/blob/v1.18.1/LICENSE.txt)
- [Pint 0.26.1 release metadata](https://pypi.org/project/Pint/0.26.1/) and [license](https://github.com/hgrecco/pint/blob/0.26.1/LICENSE)
- [GeographicLib 2.1 release metadata](https://pypi.org/project/geographiclib/2.1/) and [documentation](https://geographiclib.sourceforge.io/Python/doc/)
- [NumPy array flags](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.setflags.html)
- [AHRS metadata](https://pypi.org/project/AHRS/0.4.0/) and [pyproj metadata](https://pypi.org/project/pyproj/3.8.0/)

Context7 was used for NumPy ownership and SciPy/Pint boundaries. Primary release
metadata and installed wheel files, rather than a documentation version alone,
establish the version-specific audit facts. Temporary evidence remains in `.tmp/`.

## Stage 3 adoption — 2026-10-17

The separately instructed frame stage adopts SciPy 1.18.1 in the analysis extra,
retaining existing NumPy versions. The candidate audit table describes evaluation scope; SciPy is
root-locked/installed for passive rotation. Filtering/interpolation and
GeographicLib remain deferred. [ADR 0005](0005-passive-frame-transforms.md) and
[Stage 3 validation](../validation/M3_STAGE3.md) record current integration,
license notices, metadata limits and numerical/capability tests. No verified
real-source coordinate mapping is established by this adoption.
