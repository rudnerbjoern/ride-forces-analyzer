# ADR 0001 — Offline Windows and Python

Status: Accepted.

We will use Python 3.13, PySide6, uv, pytest, Ruff, mypy. Sensor capture is out of scope; `.forces` is the import boundary. Analysis and export are decoupled from Qt. Original files remain unmodified. FFmpeg integration and packaging are deferred until later milestones.
