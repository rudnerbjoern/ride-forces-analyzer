# Local delivery validation

Scope: current desktop, export and Windows-packaging changes on
`feat/windows-release-packages`, based on `5555f57`; version 0.1.0.
Platform: native Windows x64, Python 3.14.6, Qt/PySide6 6.12.0,
PyInstaller 6.22.3, Node 26.11.1. Original recordings remain unchanged.

## Local checks

- `uv sync --locked --all-extras --group dev --group build` and
  `uv lock --check`: passed; 44 locked packages, installed environment unchanged.
- `ruff check .`, `ruff format --check src tests`, `mypy src`:
  passed; 109 formatted files and 64 typed source files.
- `npm run typecheck`: no errors or warnings.
- `npm run test:types`, `npm run test:dependencies` and
  `node --test tests/ci/changes.test.mjs`: 11, 20 and 45 tests passed.
- `pytest -ra --durations=20 --junitxml=.tmp/test-results/application.xml --basetemp=.tmp/pytest-full-delivery`:
  all 1,519 application tests passed, including native GUI and recording integrity.
- Separate delivery-tool checks: Ruff check/format, mypy on the helper/tests and
  `pytest .agents/skills/github-delivery/tests -ra --basetemp=.tmp/pytest-skill-delivery`:
  passed; 81 tool tests. Application discovery remains separate.
- `actionlint -verbose -shellcheck= -pyflakes=`: no errors in three workflows.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .github/scripts/test-gitleaks.ps1`:
  scanner detection, deleted-secret history and complete redaction passed.
- `gitleaks git --log-opts=--all --redact=100 --no-banner --no-color --exit-code 1`
  and `gitleaks dir packaging --redact=100 --no-banner --no-color --exit-code 1`:
  no findings in existing history or new packaging materials.
- `uv build --out-dir .tmp/delivery-python-packages`: source distribution and
  wheel built successfully.
- `npm run test:docs`: Markdown, spelling and 52 link tests passed.

Native executables from the locked environment ran directly where using
`uv run` would unnecessarily resynchronize the shared test environment.
Runner output is retained in `.tmp/delivery-*.log`.

## Windows downloads

`python -m scripts.build_windows --release` built the standalone EXE, standard
ZIP, complete ZIP, available upstream sources and SHA-256 manifest.
`python -m scripts.check_windows_packages .tmp/windows-build/assets --recording tests/fixtures/real/Manta-017E20DC-422C-4844-9CE8-0CFCDDFE64F4.forces`
checks actual executables, archive contents and hashes. All three executables
passed isolated startup, German/light UI, 9,640-sample import and 4K rendering;
the complete ZIP also passed CPU video encoding with its adjacent FFmpeg.

Artifacts under `.tmp/windows-build/assets/`: EXE 78,603,081 bytes;
standard ZIP 78,730,845 bytes; complete ZIP 168,979,184 bytes; available upstream
sources ZIP 461,702,979 bytes. Exact hashes are in `WINDOWS-SHA256SUMS.txt`.

## Limits

Missing Qt PDF and complete static FFmpeg source/notice material is documented
in the included redistribution catalog and does not block package construction.
This is not a completed license review, clean-VM or code-signing qualification.
No new tag or public release was created. Hosted PR outcomes belong in PR metadata.
