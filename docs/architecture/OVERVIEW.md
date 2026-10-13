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

Boundaries: `domain` holds representations; `importers` handles external formats; `analysis` contains calibration/math; `storage` local library; `playback` timeline; `rendering` frame model and encoding; `ui` Qt widgets. This is scaffolding, not implemented product functionality.

No network connectivity required. Preserve original bytes, original coordinates and schema version. Recording time may be inferred from sample rate only if verified; keep original metadata. GPS negative speed represents unavailable data, not travel in reverse. Avoid claims of sensor accuracy or Ride Forces algorithm equivalence before empirical validation.

### Export policy
Standalone video: opaque MP4/H.264. Transparent overlay: PNG RGBA frame sequence as baseline, optional compatible alpha video codec after DaVinci Resolve tests. Frame renderer and encoder must be independent.
