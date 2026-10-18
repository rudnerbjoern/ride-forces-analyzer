# Release validation

Scope: version 0.2.0 on `release/v0.2.0`, based on `a06386e`.
Platform: native Windows x64, Python 3.14.6, Qt/PySide6 6.12.0,
PyInstaller 6.22.3, uv 0.13.0 and Node 26.11.1.

## Local checks

- `uv lock --check`: passed; only the project version changed in the lockfile.
- `ruff check .`, `ruff format --check src tests`, `mypy src`:
  passed; 109 formatted files and 64 typed source files.
- `npm run typecheck`: no errors or warnings.
- `npm run test:types`, `npm run test:dependencies`,
  `node --test tests/ci/changes.test.mjs`: 11, 20 and 45 tests passed.
- `pytest -ra --durations=20 --junitxml=.tmp/test-results/v020-application.xml --basetemp=.tmp/pytest-v020`:
  all 1,519 application tests passed, including native GUI and original recording
  byte-length/SHA-256 checks. No recording data changed.
- `pytest .agents/skills/github-delivery/tests -ra --basetemp=.tmp/pytest-skill-v020`:
  all 81 separate delivery-tool tests passed.
- `uv build --out-dir .tmp/v020-python-packages`: version 0.2.0 wheel and source
  distribution built successfully.
- `npm run test:docs`: Markdown, spelling and local-link checks passed.

Native executables from the locked environment ran directly to avoid repeated
environment synchronization. Runner evidence is retained in `.tmp/v020-*.log`.
Hosted PR and tag-workflow results are separate evidence in GitHub.

## Windows downloads

`python -m scripts.build_windows --release --work .tmp/v020-windows-build` built
the standalone EXE, standard ZIP, complete ZIP, available upstream sources and
SHA-256 manifest. The actual package check was:

```powershell
python -m scripts.check_windows_packages .tmp/v020-windows-build/assets --recording tests/fixtures/real/Manta-017E20DC-422C-4844-9CE8-0CFCDDFE64F4.forces
```

All three executables reported version 0.2.0 and passed isolated visible GUI
startup, German/light presentation, 9,640-sample import and 4K rendering. The
complete ZIP also passed CPU video encoding using its adjacent FFmpeg.
ZIP contents, notices and all manifest hashes passed verification.

Local candidate sizes: EXE 78,602,628 bytes; standard ZIP 78,730,155 bytes;
complete ZIP 168,978,494 bytes; available upstream sources ZIP 461,702,979 bytes.
Hosted builds can differ in size; their own checksum manifests are authoritative.

## Limits

Missing Qt PDF and complete static FFmpeg source/notice material remains recorded
in the included redistribution catalog. This is not a completed license review,
clean-VM or code-signing qualification. The release policy classifies 0.2.0 as a
prerelease. Public release acceptance additionally requires a successful tag
workflow and verification of the attached Source, EXE and both ZIP downloads.
