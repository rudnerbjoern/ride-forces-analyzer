# ADR 0001 — Offline Windows and Python

Status: Accepted.

## Decision

Use Windows, Python 3.14.6, uv and PySide6 for an offline desktop application.
Sensor capture is out of scope; `.forces` is the planned import boundary.
Analysis and export are decoupled from Qt, and original recording bytes remain
unmodified. FFmpeg integration and standalone packaging are deferred to M6/M8.

Pydantic validates M1 bootstrap settings outside widgets. Ruff provides linting
and formatting, mypy provides strict source checks, and Pylance/Pyright share
strict workspace typing settings. pytest covers runtime contracts and native Qt
startup. Node.js provides development-only type-contract and documentation checks;
it is not required by the application runtime.

## Revision and reproducibility

Updated 2026-10-13: Python 3.14.6 replaces the original 3.13 target at the owner's
request. Project metadata permits Python 3.14.6 and later 3.14 patches; local setup
and CI pin 3.14.6. `uv.lock` records Python dependencies, `package-lock.json` records
Node development dependencies and `.node-version` pins the validation runtime.
See [development setup](../development/SETUP.md) for the reproducible workflow.
