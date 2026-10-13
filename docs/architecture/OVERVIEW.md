# Architecture

```text
Ride Forces iPhone app -> original .forces file (read-only)
   -> version-aware importer (M2)
   -> canonical session and raw sequences (M2)
   -> calibrated analysis (M3)
   -> GUI/Playback (M4/M5)
   -> render frame engine -> MP4 / alpha overlay / PNG sequence (M6)
   -> POV video sync (M7)
```

Boundaries: `domain` holds representations; `importers` handles external formats; `analysis`
contains calibration/math; `storage` local library; `playback` timeline; `rendering` frame model and
encoding; `ui` Qt widgets. M1 established these boundaries; M2 Stage 1 implements
representations and Stage 3 adds pure motion validation over those source envelopes.
Stage 2 adds strict source decoding; Stage 4 adds optional metadata/attributes/GPS.
Stage 5 provides the full typed import service. Analysis, storage, playback
and rendering services remain planned.

Application processing requires no network connectivity. Initial development installation
may require downloads. Preserve original bytes, coordinates, unknown fields and schema metadata.
Recording time may be inferred from sample rate only after verification against the source app.
Axis polarity, filtering, calibration and GPS sentinel meanings, including negative speed,
remain **unverified**. Document and cross-check them before implementing M2/M3. Avoid claims
of sensor accuracy or Ride Forces algorithm equivalence before empirical validation.

## Planned export policy (M6)

Standalone video: opaque MP4/H.264. Transparent overlay: PNG RGBA frame sequence as baseline,
optional compatible alpha video codec after DaVinci Resolve tests. Frame renderer and encoder must
be independent.

## Implemented M1 foundation

The executable entry point and bootstrap settings remain the implemented M1 behavior.
M2 adds domain/source representations, validated subsets and the read-only import
service below. Analysis, persistence, playback and rendering remain planned.

The supported runtime is Python 3.14 (minimum 3.14.6); `.python-version` and CI select 3.14.6.
`uv.lock` records runtime, development and optional dependencies. Install with
`uv sync --locked --all-extras --group dev` to reproduce the validation environment.
The GUI smoke test runs the real module entry point in an isolated process, checks
the native Windows Qt window and exits through the normal Qt event loop.
Each of the four owner-authorized recordings is guarded by its own byte-length and
SHA-256 regression check without parsing or rewriting it. The exact inventory is
verified; see the [recording catalog](../development/RECORDINGS.md). Future import
and analysis tests must use the complete authorized set.

M2 Stage 0 adds test-only recursive schema observations, including the fifth,
owner-supplied Apple Watch fixture. It adds no production importer or domain model.
[ADR 0002](../decisions/0002-forces-source-contract.md) proposes immutable source
ownership, version dispatch, device-aware capabilities, resource limits and GPS
error handling. Apple Watch gravity/GPS absence is explicit and never synthesized.

## M2 Stage 1 representations

`domain` owns immutable source envelopes and canonical recording data. Original
bytes and exact JSON number tokens remain separate from finite typed accessors.
Motion/GPS/attribute collections are copied into tuples; source dictionaries are
recursively copied into privately owned readonly mappings. Optional values and
owner-default provenance stay explicit. No Qt or scientific transformation is used.

`importers` owns structured diagnostics and immutable success/failure results.
Ordering is deterministic, and the Literal success tag supports typed control flow.
No path adapter, file decoder or schema-version dispatch is implemented here.
See [canonical models](../development/CANONICAL_MODELS.md) and
[M2 validation](../validation/M2.md).

## M2 Stage 3 motion validation

`importers.motion.parse_motion` consumes a retained SourceEnvelope and produces
a typed motion-only result with diagnostics. It validates numeric conversion,
available paired sequences, optional structural vectors and independent index
bounds without changing source values or deriving forces/time. GPS and metadata
remain in the envelope without interpretation. No complete Recording is claimed.
Stage 2 now supplies source decoding, version dispatch and resource guards below;
the motion parser remains independently callable and is composed by Stage 5 below.
See [motion contracts](../development/MOTION_PARSING.md) and
[M2 validation](../validation/M2.md).

## M2 Stage 2 strict source decoder

`importers.decoder` separates bounded local binary input from pure bytes decoding.
Iterative lexical preflight enforces resources before full tree allocation;
strict JSON hooks retain exact number tokens and reject duplicates/non-JSON constants.
Only a supported 2.2.0 root with required core shapes yields DecodeSuccess.
The result owns original bytes/provenance and the immutable tree; it is not a Recording.
Optional metadata/GPS accessors and complete importer composition are implemented below.
See [decoder contracts](../development/STRICT_DECODING.md) and
[M2 validation](../validation/M2.md).

## M2 Stage 4 optional data

`importers.optional.parse_optional_data` consumes a decoded SourceEnvelope and
returns metadata, ordered arbitrary attributes and independently indexed GPS slots.
Unknown content/exact tokens stay in the envelope. Absent riding position uses
the owner default with explicit provenance; invalid presence never defaults.
Defective optional members warn and become unavailable; defective GPS fixes retain
their source slot. Negative/suspicious GPS values survive with contextual warnings,
without units/epoch conversion or motion alignment. Local diagnostic-budget overflow
is fatal. Stage 5 shares this collector with motion to enforce an aggregate budget
before constructing a full Recording. See [optional contracts](../development/OPTIONAL_PARSING.md) and
[M2 validation](../validation/M2.md).

## M2 Stage 5 public import service

`importers.service.import_forces(Path)` and `import_forces_bytes(bytes)` compose
strict decoding, motion and optional validation into ImportSuccess/ImportFailure.
Success owns a complete immutable Recording for available capabilities, original
source/provenance and ordered diagnostics. One per-call diagnostic collector is
shared across validation workers; overflow stops generation and fails the import.
Decoder errors stop before motion; core errors stop before optional validation.
There is no shared mutable recording state, network, writing, Qt dependency or
scientific transformation. The callable service is not connected to the GUI/library.
See [public API](../development/IMPORT_SERVICE.md) and
[M2 validation](../validation/M2.md). M2 acceptance remains open.

## Bootstrap settings validation

`config.AppSettings` is an immutable, strictly validated Pydantic model for the
initial window title and dimensions (1–16,777,215 pixels, the Qt widget-size limit).
The application entry point consumes it
before starting Qt. Runtime validation lives outside widgets; no recording schema,
importer or analysis behavior is implemented by this model. Unknown settings are
rejected, while preservation of unknown recording fields remains a distinct M2
contract. Pylance and Pyright share strict type-checking settings in `pyproject.toml`.

See [development setup](../development/SETUP.md) for commands and
[M1 validation](../validation/M1.md) for verified acceptance evidence and validation limits.
