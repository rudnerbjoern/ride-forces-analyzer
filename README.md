# Ride Forces Analyzer

Planned offline Windows application for importing Ride Forces (`.forces`) recordings,
analyzing G-force traces and producing animated charts and transparent video overlays.

**Current scope:** M1 provides an executable minimal Qt window, validated startup settings,
separate subsystem packages, tests and development tooling. Import, analysis, storage,
playback and rendering are **planned**, not implemented. M1 remains **open** until the
updated pull-request CI passes and the reviewed documentation is committed.

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
pull requests and has separate Python quality and documentation jobs.

## Documentation

Start with the [documentation index](docs/README.md). Key references:

- [AGENTS.md](AGENTS.md): repository instructions for coding agents.
- [Roadmap](docs/ROADMAP.md): milestone scope and acceptance criteria.
- [Architecture](docs/architecture/OVERVIEW.md): current foundation and planned boundaries.
- [M1 validation](docs/validation/M1.md): verified results and explicitly open criteria.

## Recording test data

`tests/fixtures/real/Manta-017E20DC-422C-4844-9CE8-0CFCDDFE64F4.forces` is included
unaltered with authentic GPS data by express permission of its owner. All recordings
are read-only inputs. A regression test compares this fixture with its original SHA-256.
Do not add or publish other personal/location recordings without authorization.
