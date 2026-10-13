# Instructions for Codex

- Implement one milestone at a time. Do not label work complete until acceptance criteria are verified.
- Target Python 3.13, Windows, uv, PySide6, typed Python, Ruff, mypy and pytest.
- Keep domain/import/analysis/storage/playback/rendering logic out of UI widgets.
- Use `.forces` recordings as **read-only** input; never rewrite them in place.
- Preserve unknown JSON fields and the original file bytes; do not assume the source schema is stable.
- Real recording fixture `tests/fixtures/real/Manta-017E20DC-422C-4844-9CE8-0CFCDDFE64F4.forces` contains authentic GPS positions, expressly authorized by the owner. Do not publish additional location recordings automatically.
- Domain coordinates and time base require explicit documentation, fixtures and cross-checks against the original Ride Forces app. Never silently assume axis polarity or filtering.
- Separate render frame generation from encoding; support independent alpha-overlay and opaque-video outputs.
- All processing must work offline. Avoid mandatory cloud services.
- Provide regression tests for bug fixes and update docs when design changes.
- Before commit run: `uv run ruff check .`, `uv run mypy src`, `uv run pytest`.
- Do not claim GUI operation or Windows CI success without actually testing those environments.
- Any feature not implemented must be clearly marked as planned.
