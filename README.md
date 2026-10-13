# Ride Forces Analyzer

Offline Windows application for importing Ride Forces (`.forces`) recordings, analyzing G-force traces and producing animated charts and transparent video overlays.

> **Status:** M1 bootstrap. Import, analysis, playback and rendering are **not implemented** yet. The Manta `.forces` file is a test fixture for future milestones.

## Requirements

- Windows 10/11, Python 3.13 and [uv](https://docs.astral.sh/uv/)
- For video exporting in later milestones, FFmpeg (not needed for M1)

## Local setup

```powershell
uv sync --group dev
uv run python -m ride_forces_analyzer
uv run pytest
uv run ruff check .
uv run mypy src
```

The graphical application requires a Windows desktop session and a Qt-capable display.

## Recording test data

`tests/fixtures/real/Manta-017E20DC-422C-4844-9CE8-0CFCDDFE64F4.forces` is included **unaltered**, with real GPS data by express permission of its owner. Treat all real fixtures as potentially personal/location data. Avoid putting new customer recordings into the repository without authorization.

## Development

Read [AGENTS.md](AGENTS.md), [roadmap](docs/ROADMAP.md), and [architecture](docs/architecture/OVERVIEW.md).
