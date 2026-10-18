# Releases

The [release workflow](../../.github/workflows/source-release.yml) handles
owner-authorized pushes of `v*` tags on native Windows. It prepares source, a
standalone Windows x64 EXE and standard/complete ZIPs. Binary publication is
accompanied by documented missing redistribution material below. Version 0.2.0
provides these portable downloads; no installer is included.
Local acceptance and owner review still precede tag creation; CI is secondary
validation. [Windows setup](SETUP.md) owns the required local checks.

## Release policy

- The tag must exactly equal `v` plus `project.version`. Supported versions are
  three numeric components, optionally followed by an `a`, `b` or `rc` number.
- The tag, event SHA and checkout must identify the same commit. The commit must
  be contained in `origin/main` and associated with a merged PR targeting this
  repository's `main`. Full CI, including mandatory Gitleaks history scanning,
  must pass for that same revision.
- All `0.x` versions and versions with `a`, `b` or `rc` suffixes are prereleases.
  Plain versions from `1.0.0` onward are stable releases.
- Source validation checks license/setup files, rejects local/binary artifacts,
  and verifies all original recording bytes against the fixture inventory.
  Wheel and source-distribution builds must also succeed.
- Only the publication job receives `contents: write`. It downloads this run's
  verified source ZIP, checksum and notes, checks the ZIP checksum, and rechecks
  the remote tag target immediately before publication.
- Publication uses `gh release create --verify-tag`, attaches the ZIP/checksum and
  combines the maintained [release text](RELEASE_NOTES.md) with generated change
  notes. Existing releases are not edited or overwritten; failed or ambiguous
  publication requires remote-state inspection before retrying.

The tag target is rechecked before publication; this is not an atomic lock against
concurrent remote tag changes. Do not move published version tags.

## In-application update discovery

The About dialog offers a manual release check and an opt-in startup check
(disabled by default). Startup checks run in a worker at most once per 24 hours;
attempts, including failures, are recorded in `preferences.sqlite3`. It also stores
the opt-in and one skipped tag. Manual checks bypass the interval and skipped tag.
Only published releases with an uploaded repository download qualify. The highest
newer supported version is selected numerically, including `0.x` and `a`/`b`/`rc`
prereleases; bare tags, drafts and releases without downloads do not qualify.

The public GitHub Releases API uses unauthenticated HTTPS without recording data
or paths. Checks bound pages (five of 100), response bytes (2 MiB per page), socket
timeout (five seconds) and a 20-second read budget checked between chunks/requests.
Limit exhaustion is an unavailable check, never a false up-to-date result.
Automatic failures are silent; manual failures provide a retry-later message.
The popup opens the validated repository release URL in the browser, postpones
the notice, or saves the skipped tag. Nothing downloads or installs automatically.

## Windows packages

PyInstaller is a pinned build-group dependency, not an application dependency.
The EXE embeds Python, imported runtime libraries, Qt plugins/translations and
collected notices. Both ZIPs contain that same EXE and external license files;
the complete ZIP additionally contains the pinned publisher's `ffmpeg.exe`,
LICENSE/README and actual license/build-configuration output. It excludes ffplay
and ffprobe. The adjacent encoder takes precedence over PATH in frozen builds;
an explicit user-selected encoder still wins. Preferences remain in LOCALAPPDATA.

```powershell
uv sync --locked --all-extras --group dev --group build
uv run --locked --group build python -m scripts.build_windows
uv run --locked --group build python -m scripts.check_windows_packages .tmp/windows-build/assets --recording (Get-ChildItem tests/fixtures/real/Manta-*.forces | Select-Object -First 1).FullName
```

Candidate files under `.tmp/windows-build/assets` are named
`Ride-Forces-Analyzer-VERSION-windows-x64.exe`, `…-standard.zip`, `…-complete.zip`
and `WINDOWS-SHA256SUMS.txt`. The checker verifies ZIP paths, required files,
source-data exclusions and hashes, then runs each actual EXE in an isolated folder
with Python/Qt environment overrides removed and PATH limited to Windows System32.
It exercises the visible GUI, German/light presentation, real recording import,
4K rendering and a real CPU encode using the complete package's encoder.
This is native workstation validation, not a clean-VM or signing qualification.

**Documented missing material:** `packaging/redistribution.json` is pending. Official
Qt/PySide 6.12.0 sources are downloaded and pinned; a static
[Qt notice file](../../packaging/QT-NOTICES.txt) is included by the existing
notice collector. Sources/notices for the automatically bundled Qt PDF plugin and
complete corresponding sources/build instructions for the static GyanD FFmpeg
binary's libraries remain missing. Generic upstream links do not close those gaps.
The catalog is included in the EXE and both ZIPs. These recorded gaps do not
block package construction; they remain unresolved license/source obligations.

`--release` reports the documented gaps and verifies the supplied source archives'
SHA-256 values. It downloads configured HTTPS sources only into
`.tmp/`, and assembles `corresponding-sources.zip` for the same release. The Windows
job and package execution checks must succeed before the publication job can run.
Publication rechecks all downloaded asset hashes and the live tag, then attaches
the source ZIP, EXE, both Windows ZIPs, checksums and corresponding sources. A
documented missing provider source does not block the workflow. Missing or modified
files that are explicitly listed in the catalog still fail verification.
Version 0.2.0 uses this path for all four user-facing download variants.

## Distribution boundaries

The program is GPL-3.0-or-later. The five authorized full recordings, including
GPS/metadata, and the listed documentation images have separate CC BY-SA 4.0 grants.
Original bytes and attribution notices remain intact. See
[third-party notices](../../THIRD_PARTY_NOTICES.md) before any future binary bundle.

Actions artifacts are retained for 14 days; attached GitHub release assets are
separate downloads. Existing tags do not trigger the workflow retroactively.
Each release requires a successful tag workflow and verification of its attached assets.
