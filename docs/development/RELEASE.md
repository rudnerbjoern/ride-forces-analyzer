# Releases

<!-- cspell:words libegl libopengl libxcb libxkbcommon -->

The [release workflow](../../.github/workflows/source-release.yml) handles
owner-authorized pushes of `v*` tags. Windows remains the development environment;
Linux/macOS packages are built and executed by native target workers in reusable CI.
The workflow validates tagged sources and prepares a standalone Windows x64 EXE,
standard/complete ZIPs, a Linux x64 tarball and macOS arm64/x64 app ZIPs. Binary publication is
accompanied by documented missing redistribution material below. Published version
0.4.0 provides Windows downloads; the next release can include all native targets.
No installer is included.
Local acceptance and owner review still precede tag creation; CI is secondary
validation. [Windows setup](SETUP.md) owns the required local checks.

## Release policy

- The tag must exactly equal `v` plus `project.version`. Supported versions are
  three numeric components, optionally followed by an `a`, `b` or `rc` number.
- The tag, resolved release SHA and source checkout must identify the same commit. The commit must
  be contained in `origin/main` and associated with a merged PR targeting this
  repository's `main`. Full CI, including mandatory Gitleaks history scanning,
  must pass for that same revision.
- All `0.x` versions and versions with `a`, `b` or `rc` suffixes are prereleases.
  Plain versions from `1.0.0` onward are stable releases.
- Source validation checks license/setup files, rejects local/binary artifacts,
  and verifies all original recording bytes against the fixture inventory.
  Wheel and source-distribution builds must also succeed.
- Only the publication job receives `contents: write`. It downloads this run's
  verified native packages, platform checksum files and notes, verifies all package hashes,
  and rechecks the remote tag target immediately before publication.
- Publication uses `gh release create --verify-tag`, attaches all native downloads and checksum files, and
  combines the maintained [release text](RELEASE_NOTES.md) with generated change
  notes. Existing releases are not edited or overwritten; failed or ambiguous
  publication requires remote-state inspection before retrying.

GitHub supplies the release's **Source code (zip)** and **Source code (tar.gz)**
downloads automatically; see [GitHub's release documentation](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
The workflow's temporary source archive is used only for validation and is not
uploaded or attached to the release.

The tag target is rechecked before publication; this is not an atomic lock against
concurrent remote tag changes. Do not move published version tags.

To retry publication of an existing tag after a workflow correction, dispatch the
current workflow from `main` with the `tag` input, for example:

```powershell
gh workflow run source-release.yml --ref main -f tag=v0.4.0
```

Quality checks use the current workflow definition and check out the resolved
tagged commit. Source validation and all native builds use that same commit,
with the same ancestry, merged-PR,
version and checksum gates. Concurrent runs for the same tag are serialized.
Native package artifacts are downloaded without automatic decompression so their
original filenames, bytes and checksums remain intact. Existing releases are
never overwritten by this retry path.

## In-application update discovery

The About dialog offers a manual release check and an opt-in startup check
(disabled by default). Startup checks run in a worker at most once per 24 hours;
attempts, including failures, are recorded in `preferences.sqlite3`. It also stores
the opt-in and one skipped tag. Manual checks bypass the interval and skipped tag.
Only published releases with an uploaded application download for the running
OS/architecture qualify; source archives and checksums alone do not. The highest
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
`.tmp/`; those dependency archives are not bundled as a release download. The Windows
job and package execution checks must succeed before the publication job can run.
Publication rechecks all downloaded asset hashes and the live tag, then attaches
the EXE, both Windows ZIPs, Linux/macOS packages and platform checksum files. A
documented missing provider source does not block the workflow. Missing or modified
files that are explicitly listed in the catalog still fail verification.
Version 0.4.0 provides the three Windows application downloads and their checksum file.

## Linux and macOS packages

These targets are prepared for a future release. Published `v0.4.0` remains
Windows-only; never move its tag or overwrite its assets to add these changes.
Development and the full local regression suite stay on Windows. Native package
builds require their own OS; Windows mocks do not establish macOS acceptance.

| Target              | Download                                        | Minimum target / installation                                                                                            |
| ------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Linux x64           | `Ride-Forces-Analyzer-VERSION-linux-x64.tar.gz` | Ubuntu 24.04 / glibc 2.39; extract and execute `./Ride-Forces-Analyzer` inside its directory; keep `_internal` beside it |
| macOS Apple Silicon | `Ride-Forces-Analyzer-VERSION-macos-arm64.zip`  | macOS 15+; extract and move `Ride-Forces-Analyzer.app` to Applications                                                   |
| macOS Intel         | `Ride-Forces-Analyzer-VERSION-macos-x64.zip`    | macOS 15+; extract and move `Ride-Forces-Analyzer.app` to Applications                                                   |

Native packages embed Python, Qt and collected notices, but do not bundle FFmpeg.
Linux desktop runtime dependencies on Ubuntu are `libegl1`, `libopengl0`,
`libxcb-cursor0` and `libxkbcommon-x11-0`; a working X11 or Wayland session is required.
Install FFmpeg separately (`sudo apt install ffmpeg` on Ubuntu, or an existing
compatible macOS installation such as `brew install ffmpeg`). PATH discovery or
the export assistant's Browse action selects it. CPU H.264 and ProRes 4444 encoding
are checked; NVIDIA acceleration is optional and capability-probed, not assumed.

macOS apps use PyInstaller's ad-hoc signatures. They are not notarized or signed
with an Apple Developer ID. After checking the download hash, macOS may require
an explicit **Open Anyway** approval in Privacy & Security for a trusted download.
Do not disable Gatekeeper globally. Each architecture is built separately from
its matching locked wheels; a universal app is not claimed.

Native build workers run these existing entry points:

```sh
uv sync --locked --all-extras --group dev --group build
uv run --locked --group build python -m scripts.build_posix
uv run --locked --group build python -m scripts.check_posix_packages .tmp/posix-build/assets --recording /absolute/path/to/authorized/Manta.forces
```

The actual recording path is supplied by the workflow from the unchanged fixture
catalog. Linux CI uses Xvfb; macOS uses the hosted desktop. Both execute the
extracted frozen package with isolated user state, a read-only launch directory,
real import, German/light UI, 4K rendering and an external CPU encode. The macOS
checker additionally verifies the extracted app signature. No offscreen result
substitutes for these native gates.

Each target emits its own `LINUX-X64-SHA256SUMS.txt`,
`MACOS-ARM64-SHA256SUMS.txt` or `MACOS-X64-SHA256SUMS.txt`. Publication downloads
verified artifacts from the same run without unpacking them, validates every
platform's complete checksum inventory and publishes only after the required
native CI gate and Windows package checks succeed.

Preferences/export databases use `~/.local/share/ride-forces-analyzer` on Linux
(or absolute XDG_DATA_HOME) and `~/Library/Application Support/Ride Forces Analyzer`
on macOS. No recording or user data is installed in the app bundle. Rendering
uses Pillow's scalable font fallback when Segoe UI is absent; glyph metrics need
not be pixel-identical to Windows. Existing redistribution gaps remain documented
in the shipped catalog; no static Windows FFmpeg binary is added to these packages.

## Distribution boundaries

The program is GPL-3.0-or-later. The five authorized full recordings, including
GPS/metadata, and the listed documentation images have separate CC BY-SA 4.0 grants.
Original bytes and attribution notices remain intact. See
[third-party notices](../../THIRD_PARTY_NOTICES.md) before any future binary bundle.

Actions artifacts are retained for 14 days; attached GitHub release assets are
separate downloads. Existing tags do not trigger the workflow retroactively.
Each release requires a successful tag workflow and verification of its attached assets.
