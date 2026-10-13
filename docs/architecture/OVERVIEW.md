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
encoding; `ui` Qt widgets. This is scaffolding, not implemented product functionality.

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

Only the executable entry point and bootstrap settings have behavior in M1; the subsystem
packages are placeholders. No importer, analysis, persistence, playback or renderer exists yet.

The supported runtime is Python 3.14 (minimum 3.14.6); `.python-version` and CI select 3.14.6.
`uv.lock` records runtime, development and optional dependencies. Install with
`uv sync --locked --all-extras --group dev` to reproduce the validation environment.
The GUI smoke test runs the real module entry point in an isolated process, checks
the native Windows Qt window and exits through the normal Qt event loop.
Fixture integrity is guarded by a SHA-256 regression test without parsing or rewriting it.

## Bootstrap settings validation

`config.AppSettings` is an immutable, strictly validated Pydantic model for the
initial window title and dimensions (1–16,777,215 pixels, the Qt widget-size limit). The application entry point consumes it
before starting Qt. Runtime validation lives outside widgets; no recording schema,
importer or analysis behavior is implemented by this model. Unknown settings are
rejected, while preservation of unknown recording fields remains a distinct M2
contract. Pylance and Pyright share strict type-checking settings in `pyproject.toml`.

See [development setup](../development/SETUP.md) for commands and
[M1 validation](../validation/M1.md) for verified evidence and open acceptance criteria.
