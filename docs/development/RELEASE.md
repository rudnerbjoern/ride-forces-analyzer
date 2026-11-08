# Releases

Developer guide to release policy, packages and publication.
[Installation](../user/INSTALLATION.md) covers downloads, first launch and FFmpeg;
[Windows setup](SETUP.md) owns local checks; the [roadmap](../ROADMAP.md) owns milestones.

## Prepare versions

Use the [preparation script](../../scripts/prepare_release.py) with explicit targets:

```powershell
uv run --locked python -m scripts.prepare_release --app-version 2.1.0 --plugin-version 0.3.0 --dry-run
```

Review the metadata preview, then repeat without `--dry-run` to write changes and
refresh all five [reference image groups](../../.agents/skills/update-screenshots/SKILL.md).
Three screenshot scripts run in five sequential calls on the native Windows desktop.
Locked Python/Node development dependencies are required. Preview never starts generators.
Omitted targets stay unchanged; decreasing or malformed versions and inconsistent
metadata fail before writing. Write failures trigger restoration of originals;
any recovery failure is reported for manual inspection.

| Option                 | Synchronized values                                                                                     |
| ---------------------- | ------------------------------------------------------------------------------------------------------- |
| `--app-version`        | `pyproject.toml`, Python package version, root entry in `uv.lock`, README version/release status        |
| `--plugin-version`     | Independent npm package, native four-component manifest, workspace lock entry                           |
| `--control-protocol`   | Python/TypeScript application protocol, shared examples, documentation and owner-approved test baseline |
| `--transport-protocol` | Discovery/authentication version on both sides and documentation                                        |

Protocol targets require explicit owner approval; a product-version change never
updates them or their locked baseline. Historical releases, external versions and
dependency locks' unrelated entries stay unchanged. A failed generator stops
preparation with an error; written versions/images remain for inspection. Fix the
cause and repeat the same command, including unchanged targets, to finish the refresh.
The image guide's version is updated only after every generator succeeds. Review
changed images and captions using the screenshot workflow before delivery.
GitHub assigns the publication date; there is no separate release-date field.
Run affected checks after preparation. The script does not stage, commit, tag,
publish, create compatibility aliases or add migrations.

## Release policy

The [release workflow](../../.github/workflows/release.yml) supports:

| Trigger                               | Requirements                                                                                                                                                  |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Merge `release/<version>` into `main` | Same-repository PR; branch suffix matches `project.version`; live PR metadata matches event head and checked-out merge commit; successful `CI` / `check` gate |
| Push `v*` tag                         | Existing tag exactly matches `v` + `project.version` and the release commit                                                                                   |
| Manual retry                          | Existing tag; current workflow dispatched from `main`                                                                                                         |

- Local acceptance and owner review precede the release-PR merge or tag creation;
  CI is secondary validation. Versions and publication require explicit decisions;
  the workflow never increments versions. Unmerged PRs and other branches do not
  start automatic release preparation.
- Supported versions: three numeric components, optionally followed by an `a`, `b`
  or `rc` number. Stable releases use plain numeric versions and become latest.
- Release SHA, checkout and tag must agree. The commit must belong to `origin/main`
  and have an associated merged PR targeting this repository's `main`.
- Release CI, including Gitleaks history scanning, must pass. Only application/UI
  checks may reuse green PR evidence for identical content, workflow revision and
  Windows runner image; missing evidence runs fresh checks. Native builds and
  package self-tests always run. See the [CI reuse contract](CI.md#routing-and-required-gate).
- Source validation checks license/setup files, rejects local/binary artifacts and
  verifies every original recording against the fixture inventory. Wheel and
  source-distribution builds must succeed.
- Only publication receives `contents: write`. After all checks/builds, it verifies
  this run's package inventories and hashes, then creates a missing release-PR tag
  at the verified merge commit. Existing tags must match; tag pushes/manual retries
  cannot create one. The live target is rechecked before publication, without an
  atomic lock against concurrent changes. Never move published tags.
- `gh release create --verify-tag` publishes the six app downloads, plugin and five
  checksum files. Artifacts retain their original filenames/bytes without automatic
  decompression. Existing releases are never edited/overwritten; inspect remote state
  before retrying failed or ambiguous publication. Runs for the same tag or merged
  PR commit are serialized.
- Paid signing and macOS notarization are not gates; see
  [distribution constraints](../architecture/02_architecture_constraints.md#distribution-constraints).

GitHub supplies [source ZIP/tar.gz downloads](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
The temporary validation archive is never uploaded or attached.

**Retry after a workflow correction:**

```powershell
gh workflow run release.yml --ref main -f tag=v2.0.0
```

Checks use the current workflow definition and immutable workflow revision's source
validator; source validation/builds use the resolved tagged commit. All version,
ancestry, merged-PR and checksum gates still apply; no tag movement is needed.

## Automatic release notes

- GitHub generates merged PR entries, contributors and a full comparison link,
  preceded by the reusable [release introduction](RELEASE_NOTES.md).
- [Category](../../.github/release.yml) precedence: `enhancement`, `bug`,
  `documentation`, `dependencies`, `ci`, catch-all. No authors/labels are excluded.
- Use clear, user-readable PR titles and applicable `bug`/`enhancement` labels.
  Issue labels do not transfer automatically; path-based PR labels remain additive.
- Keep the introduction's installation/guide/limitation links at the release tag;
  no per-version feature list. Add **Upgrade notes** only for required user actions
  (for example, recreating incompatible presets); remove obsolete instructions.
- Review generated notes and the previous-release comparison before publication.
  See [GitHub automatic release notes](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes).

## In-application update discovery

| Behavior           | Contract                                                                                                                                                                                                            |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Settings → Updates | Manual check; opt-in startup check, off by default. Save applies the preference; Cancel preserves it.                                                                                                               |
| Startup            | Worker; at most once per 24 hours. `preferences.sqlite3` stores attempts including failures, opt-in and one skipped tag.                                                                                            |
| Manual check       | Bypasses interval and skipped tag.                                                                                                                                                                                  |
| Selection          | Numerically highest newer supported published release with an uploaded app download for this OS/architecture. Bare tags, drafts, source archives/checksums alone and releases without app downloads do not qualify. |
| Request            | Public GitHub Releases API; unauthenticated HTTPS; no recording data or paths.                                                                                                                                      |
| Limits             | Five pages of 100; 2 MiB/page; five-second socket timeout; 20-second read budget checked between chunks/requests. Exhaustion means unavailable, never up to date.                                                   |
| Failure            | Automatic: silent. Manual: retry-later message.                                                                                                                                                                     |
| Popup              | Open validated repository release URL in the browser, postpone notice or save skipped tag. No automatic download/install.                                                                                           |

## Stream Deck plugin deliverable

- Version independently of `project.version`; package, native manifest and lock
  metadata must agree. Follow the [plugin version workflow](../../plugins/stream-deck/README.md#independent-plugin-version)
  once for changed plugin code/data since the preceding release; keep that upcoming
  version across development commits. App-only releases need no plugin bump.
  Comparison uses the preceding reachable app release tag, including tagged candidates.
- Full release CI runs plugin tests and official offline validation/packing.
  `upload-packages: true` packs the tested folder without rebuilding and retains
  `Ride-Forces-Analyzer.streamDeckPlugin` plus `PLUGIN-SHA256SUMS.txt` from this run.
  Publication requires both and verifies the exact inventory/hash.
- Archive contents: self-contained runtime, license notices, icons/layouts and
  Plus/Neo/Mobile profiles. Local packing after successful tests:

```powershell
npm run pack:built-plugin --workspace plugins/stream-deck
```

For build plus pack, use `npm run pack:plugin --workspace plugins/stream-deck`.
Both write to `.tmp/stream-deck-package/`; replacing an existing archive requires
explicit `-- --force`.

[User guide](../user/STREAM_DECK.md): installation/profile selection.
Native archive installation/update, physical controls and macOS integration remain
unverified; packing/upload does not close them. Marketplace publication and automatic
plugin updates are not configured.

## Shared application icon

[`app-icon.svg`](../../src/ride_forces_analyzer/ui/presentation/app-icon.svg) supplies
window/package artwork. [`scripts.build_icons`](../../scripts/build_icons.py) uses
Qt SVG to generate temporary ICO (16–256 px), ICNS (up to 1024 px) and PNG (512 px).
Generated binaries are not maintained in source control.

| Target  | Collected artwork                                                                                                                                                                      |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| All     | SVG and runtime renderer                                                                                                                                                               |
| Windows | ICO embedded by PyInstaller                                                                                                                                                            |
| macOS   | ICNS in app bundle                                                                                                                                                                     |
| Linux   | PNG, SVG and `ride-forces-analyzer.desktop`; [optional menu setup](../user/INSTALLATION.md#optional-application-menu-shortcut) connects the portable executable to desktop icon lookup |

Native package checks require these artifacts; Windows format/command tests do not
replace Linux/macOS builds or desktop integration checks.

## File and application properties

Both builders read the version directly from `pyproject.toml`. Shared metadata: product **Ride Forces Analyzer**;
description **Ride force analysis and video overlays**; author **Björn Rudner**;
**Copyright © 2026 Björn Rudner**.

| Target  | Metadata                                                                                                                                                                                                                                                                                                                    |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Windows | UTF-8 `--version-file`: `ProductName`, `FileDescription`, author in `CompanyName`, `LegalCopyright`, `OriginalFilename`, matching `FileVersion`/`ProductVersion`. Four 16-bit numeric components; exact full-text project version; stable releases have no preview flag. English Unicode resource; UI language independent. |
| macOS   | `CFBundleName`, `CFBundleDisplayName`, both existing version keys and `NSHumanReadableCopyright`, set before signing. Custom `RideForcesAnalyzerDescription`/`RideForcesAnalyzerAuthor` fields are not automatically displayed by Finder.                                                                                   |
| Linux   | Desktop-entry `Name`/`Comment`, retaining German comment; custom `X-RideForcesAnalyzer-Version`, `X-RideForcesAnalyzer-Author`, `X-RideForcesAnalyzer-Copyright`. Standard desktop-entry `Version` is not the app version. Display depends on the desktop; ELF has no Windows-style properties resource.                    |

## Windows packages

Portable packages, without installer/uninstaller:

| Download under `.tmp/windows-build/assets/`             | Contents                                                                                                                                                                         |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Ride-Forces-Analyzer-VERSION-windows-x64.exe`          | Python, imported runtime libraries, Qt plugins/translations and collected notices                                                                                                |
| `Ride-Forces-Analyzer-VERSION-windows-x64-standard.zip` | Same EXE, project/asset notices and one `THIRD-PARTY-LICENSES.txt` dependency inventory                                                                                          |
| `Ride-Forces-Analyzer-VERSION-windows-x64-complete.zip` | Standard contents plus pinned publisher's `ffmpeg.exe`; publisher LICENSE/README and actual license/build output are included in the consolidated notice file; no ffplay/ffprobe |
| `WINDOWS-SHA256SUMS.txt`                                | Checksums for the three downloads                                                                                                                                                |

`THIRD-PARTY-LICENSES.txt` lists runtime libraries/versions, original notice sources
and component copyrights. Whitespace-equivalent license bodies appear once,
grouped by type; differing terms and exceptions remain distinct. Full package
METADATA descriptions and the copied license directory tree are omitted. The EXE
embeds the same file; native Linux/macOS bundles collect it in their runtime data.

PyInstaller is a pinned build-group dependency, not an app dependency. In frozen
builds, an explicit encoder choice wins over adjacent FFmpeg, which wins over PATH.
Preferences remain in LOCALAPPDATA.

```powershell
uv sync --locked --all-extras --group dev --group build
uv run --locked --group build python -m scripts.build_windows --release
```

**Local validation:** follow the [release skill](../../.agents/skills/release/SKILL.md#3-build-candidates-and-execute-the-local-exe):
reuse valid application/UI evidence, build once, run the standalone EXE self-test.
**CI validation:** execute all three packages; do not add this as a local gate:

```powershell
uv run --locked --group build python -m scripts.check_windows_packages .tmp/windows-build/assets --recording (Get-ChildItem tests/fixtures/real/Manta-*.forces | Select-Object -First 1).FullName
```

The checker validates ZIP paths, required files, source-data exclusions and hashes.
Each actual EXE runs in an isolated folder, without Python/Qt overrides and with a
System32-only PATH: visible German/light GUI, real recording import, 4K rendering
and real CPU encoding with the complete package's encoder. This establishes native
workstation validation, not clean-machine compatibility across supported packages/targets.

**Accepted redistribution scope:**

- `packaging/redistribution.json` is accepted and included in the consolidated
  notice file in the EXE/both ZIPs;
  [third-party notices](../../THIRD_PARTY_NOTICES.md) own notices to check before future bundles.
- Official Qt/PySide 6.12.0 sources are downloaded/pinned; the existing collector
  consolidates the original [Qt notices](../../packaging/QT-NOTICES.txt).
  All targets' shared GUI hook excludes the unused PDF image plugin;
  self-tests verify its absence before import/rendering. Other image plugins and
  standard GUI dependencies remain.
- Existing FFmpeg delivery is owner-accepted; no additional source bundle is planned.
  Completeness of corresponding sources/build instructions for FFmpeg and linked
  libraries is not independently verified. The catalog records this accepted scope
  and limitation. This limitation does not block release; acceptance does not establish
  license compliance.
- `--release` verifies listed source archives' SHA-256 values and downloads configured
  HTTPS sources only into `.tmp/`. Dependency archives are not release downloads.
  Missing/modified catalog-listed files fail verification.

## Linux and macOS packages

Development/local regression stay on Windows; each target builds/executes natively
with matching locked wheels. Windows mocks establish no macOS acceptance; no universal
app is claimed.

| Target              | Download                                        | Minimum target            | Checksums                    |
| ------------------- | ----------------------------------------------- | ------------------------- | ---------------------------- |
| Linux x64           | `Ride-Forces-Analyzer-VERSION-linux-x64.tar.gz` | Ubuntu 24.04 / glibc 2.39 | `LINUX-X64-SHA256SUMS.txt`   |
| macOS Apple Silicon | `Ride-Forces-Analyzer-VERSION-macos-arm64.zip`  | macOS 15+                 | `MACOS-ARM64-SHA256SUMS.txt` |
| macOS Intel         | `Ride-Forces-Analyzer-VERSION-macos-x64.zip`    | macOS 15+                 | `MACOS-X64-SHA256SUMS.txt`   |

Packages embed Python, Qt and notices; no bundled FFmpeg or static Windows encoder.
[Installation](../user/INSTALLATION.md) owns desktop dependencies, external FFmpeg
and OS approvals. Smoke checks use CPU H.264; NVIDIA acceleration is optional and
capability-probed.

**On native build workers:**

```sh
uv sync --locked --all-extras --group dev --group build
uv run --locked --group build python -m scripts.build_posix
uv run --locked --group build python -m scripts.check_posix_packages .tmp/posix-build/assets --recording /absolute/path/to/authorized/Manta.forces
```

The workflow supplies the real path from the unchanged fixture catalog.
Linux uses Xvfb; macOS uses the hosted desktop. Checks run extracted frozen packages
with isolated user state and a read-only launch directory: real import, German/light
GUI, 4K rendering, external CPU encode and, on macOS, app-signature verification.
Offscreen checks do not substitute for these gates. Publication requires native CI
and Windows package checks to pass.

No recording/user data is installed in app bundles; [deployment](../architecture/07_deployment_view.md#local-export-configuration)
owns data paths. Pillow's scalable font fallback handles missing Segoe UI; metrics
need not match Windows pixels. The shipped catalog retains the accepted redistribution scope.

## Distribution boundaries

- Program: GPL-3.0-or-later. Authorized recordings, app exports, documentation images
  and bundled POV photographs follow the [central owner grant](../../ASSET_LICENSES.md);
  preserve original bytes and attribution.
- Actions artifacts: 14-day retention; attached GitHub release assets are separate downloads.
- Existing tags do not trigger workflows retroactively. Every release requires a
  successful release workflow and verification of attached assets.
