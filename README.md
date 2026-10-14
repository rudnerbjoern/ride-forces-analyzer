# Ride Forces Analyzer

Planned offline Windows application for importing Ride Forces (`.forces`) recordings,
analyzing G-force traces and producing animated charts and transparent video overlays.

**Current scope:** M1 provides an executable minimal Qt window, validated startup settings,
separate subsystem packages, tests and development tooling. M2 Stage 1 adds
immutable canonical models and structured diagnostics for synthetic construction;
see the [model guide](docs/development/CANONICAL_MODELS.md). Stage 3 adds
[motion validation](docs/development/MOTION_PARSING.md) over supplied source trees.
Stage 2 adds [strict source decoding](docs/development/STRICT_DECODING.md) from
read-only paths or bytes. Stage 4 adds [optional metadata, attributes and GPS parsing](docs/development/OPTIONAL_PARSING.md),
with explicit absence and owner-default provenance. Stage 5 exposes the
[public read-only import service](docs/development/IMPORT_SERVICE.md), returning
complete typed recordings for their available data. Calibrated analysis, storage, playback,
GUI importing and rendering remain **planned**. M2 acceptance is verified;
see the [final validation](docs/validation/M2.md).
M3 Stage 1 adds [immutable analysis contracts](docs/development/ANALYSIS_MODELS.md)
and an isolated scientific-library audit. Source units/calibration remain unverified;
Stage 2 adds explicitly qualified DEVICE vectors/norms and Pint conversion in
`analysis.device`. Real-recording units remain unqualified; rider/world calculations,
filtering and GPS analysis remain planned.
**M1 acceptance is verified**
on Windows and in pull-request CI, and
[PR #1](https://github.com/rudnerbjoern/ride-forces-analyzer/pull/1) is merged.

## Requirements

- Windows 10/11 with a desktop session for the native Qt application.
- Python 3.14.6 and uv 0.13.0; uv can install the managed Python interpreter.
- For development checks: Node.js 26.11.1 from `.node-version` and its bundled npm.

Node.js is a development dependency, not an application runtime dependency.
FFmpeg is planned for later export milestones and is not required for M1.

## Quick start

From the repository root in Windows PowerShell, with uv available:

```powershell
uv python install 3.14.6
uv sync --locked --all-extras --group dev
uv run python -m ride_forces_analyzer
```

The last command opens the M1 window and waits until it is closed. The application
currently displays a placeholder for the planned M2 import feature.

For Node installation, the complete validation commands and VS Code Test Explorer setup,
follow the [Windows development guide](docs/development/SETUP.md). CI runs only on
pull requests and has separate application, skill and documentation jobs.

## Documentation

Start with the [documentation index](docs/README.md). Key references:

- [AGENTS.md](AGENTS.md): repository instructions for coding agents.
- [Roadmap](docs/ROADMAP.md): milestone scope and acceptance criteria.
- [arc42 architecture](docs/architecture/README.md): twelve chapters with Mermaid diagrams,
  current foundation, planned boundaries and unresolved scientific contracts.
- [M1 validation](docs/validation/M1.md): verified results and validation limits.
- [M2 validation](docs/validation/M2.md): final importer acceptance and Windows/PR CI evidence.

## Recording test data

Four genuine recordings are included in `tests/fixtures/real/`: Manta, Kraken,
Taron and Voltron Nevera. Their owner expressly authorizes using and publishing
the complete files with all embedded data, including GPS, in this project for
tests and development. Each file remains read-only and has its own byte-length
and SHA-256 regression check. See the [recording catalog](docs/development/RECORDINGS.md)
for filenames, digests and test scope. Other recordings require separate authorization.

The owner additionally supplied the Apple Watch Iron Gwazi recording for the
current M2 Stage 0 inspection. The five-file recursive inventory distinguishes
its missing gravity/GPS from the iPhone profile; see
[format observations](docs/requirements/FORMAT-ANALYSIS.md).
The callable service imports all five read-only originals; see
[M2 validation](docs/validation/M2.md).
