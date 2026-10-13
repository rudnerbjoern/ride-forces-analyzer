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
representations only.
Import, analysis, storage, playback and rendering services remain planned.

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
M2 Stage 1 adds domain and diagnostic/result representations below; there is still
no file-import service, analysis, persistence, playback or renderer.

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
[Stage 1 evidence](../validation/M2_STAGE1.md).

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
