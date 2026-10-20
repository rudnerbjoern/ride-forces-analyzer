# Third-party licenses and materials

<!-- cspell:words shiboken ast flexcache flexparser librt iniconfig pluggy dateutil tzdata libx264 libx265 nonfree Aileron GyanD WTFPL CMU QtCharts buildconf Segoe -->

Copyright © 2026 Björn Rudner. Program code: [GPL-3.0-or-later](LICENSE).
External components retain their licenses. This inventory records notice/source
duties, not a complete notice bundle or installer clearance.
Versions/hashes: [uv.lock](uv.lock), [package-lock.json](package-lock.json),
[ffmpeg.json](ffmpeg.json). Architecture owns
[deployment](docs/architecture/07_deployment_view.md);
[release documentation](docs/development/RELEASE.md#windows-packages) owns package checks.

## Python application components

Top-level metadata does not replace bundled-component notices.

| Component                                                   | Observed license                                                             | Redistribution duty                                                                                |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| PySide6, Essentials, Addons, Pdf, WebEngine; shiboken6      | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only in metadata; Qt modules differ | Retain binding/Qt/third-party notices; satisfy selected module terms                               |
| Qt Core, Gui, Widgets                                       | LGPLv3/GPLv3 options                                                         | Retain terms/source access and LGPL replacement/reverse-engineering rights where applicable        |
| **Qt Charts**                                               | **GPLv3 or commercial**, not general LGPL                                    | Imported by the application; GPL distribution of the combined binary requires corresponding source |
| pydantic, pydantic_core, annotated-types, typing-inspection | MIT                                                                          | Retain copyright/permission notices                                                                |
| typing_extensions                                           | PSF-2.0                                                                      | Retain license/notices                                                                             |
| NumPy                                                       | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 in metadata               | Retain complete wheel/native-component notices                                                     |
| SciPy, Pandas, Pint, flexcache, flexparser                  | BSD-3-Clause in inspected texts                                              | Retain copyright/conditions/disclaimers; no contributor-name endorsement                           |
| pyqtgraph, six                                              | MIT                                                                          | Retain supplied/bundled notices                                                                    |
| Pillow                                                      | MIT-CMU plus bundled licenses                                                | Retain full installed LICENSE                                                                      |
| python-dateutil                                             | Apache-2.0 / BSD notices                                                     | Retain combined license/attribution                                                                |
| tzdata                                                      | Apache-2.0 plus public-domain time-zone data notice                          | Retain both notice files                                                                           |

- [Qt licensing](https://doc.qt.io/qt-6/licensing.html) and
  [Qt Charts terms](https://doc.qt.io/qt-6/qtcharts-index.html#licenses) distinguish
  modules. The project's or-later grant neither relicenses GPL-3.0-only dependencies
  nor guarantees future-GPL compatibility of the combined application.
- [QT-NOTICES.txt](packaging/QT-NOTICES.txt) contains original Qt/PySide 6.12.0
  source-archive license/attribution texts and is included in EXE/both ZIPs.
  Installed binding metadata alone is insufficient. Source archives are pinned in
  [redistribution.json](packaging/redistribution.json).
- **Open:** those archives exclude Qt PDF/Chromium. PyInstaller collects a PDF
  plugin without a direct application import; matching sources/notices remain missing.
- Numerical wheels include native components: SciPy notices cover OpenBLAS, LAPACK
  and GCC runtime, including `GPL-3.0-or-later WITH GCC-exception-3.1`.
  Preserve that exception and NumPy's complete license collection; “BSD” alone is insufficient.
- Pillow includes image/compression/font components such as FreeType; retain full
  notices/credits for the actual binary and chosen licensing route.

## FFmpeg build

| Item               | Contract/evidence                                                                                                                                      |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Publisher          | GyanD [9.0.2 full static Windows build](https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2); archive SHA-256 pinned/checked against `ffmpeg.json` |
| License            | Encoder `-L`: GPL version 3 or later; not LGPL-only                                                                                                    |
| Build flags        | `--enable-gpl`, `--enable-version3`, `--enable-static`, `--enable-libx264`, `--enable-libx265`; no `--enable-nonfree`                                  |
| Publisher material | LICENSE and README.txt; README references source commit `946fcce07b`                                                                                   |
| Invocation         | Separate executable, no FFmpeg DLL linking in application code; binary/archive not tracked                                                             |
| Setup              | Publisher download or user-selected encoder; setup retains LICENSE/README beside `bin/`                                                                |
| Complete ZIP       | Exact pinned encoder plus publisher LICENSE/README and executable license/build output                                                                 |

Redistributing FFmpeg requires exact corresponding sources/build information and
notices for linked libraries. The README commit/generic upstream URL is not a
verified complete static-library source bundle; that gap remains open.
[FFmpeg legal guidance](https://ffmpeg.org/legal.html) describes build-dependent
licensing. Codec patent permissions are separate and not established here.

## Development and build tools

Development tools are not application imports; their notices apply when shipping
a development environment. PyInstaller's bootloader exception is relevant to binaries.

| Tool                                                                                                              | Observed license / duty                                                                                                                                   |
| ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PyInstaller                                                                                                       | Locked optional build group; GPLv2-or-later with distribution/bootloader exception; full COPYING collected in Windows packages; project license unchanged |
| ast_serialize, librt, mypy, mypy_extensions, iniconfig, platformdirs, pluggy, pytest, pytest-cov, pytest-qt, ruff | MIT; retain bundled notices, especially mypy                                                                                                              |
| coverage.py                                                                                                       | Apache-2.0; retain license/NOTICE                                                                                                                         |
| colorama                                                                                                          | BSD-3-Clause                                                                                                                                              |
| Pygments                                                                                                          | BSD-2-Clause                                                                                                                                              |
| packaging                                                                                                         | Apache-2.0 OR BSD-2-Clause                                                                                                                                |
| pathspec                                                                                                          | MPL-2.0; preserve notices/source availability for covered files                                                                                           |

Node lock entries declare MIT, ISC, BSD-2-Clause, BSD-3-Clause, WTFPL,
CC BY-SA 4.0, PSF-2.0 or Python-2.0. Entries are not unique upstream projects.

- `@cspell/dict-en-common-misspellings`: CC BY-SA 4.0; attribution/license, change
  indications and ShareAlike for adaptations.
- `@cspell/dict-django`: WTFPL. The two argparse entries declare PSF-2.0 and Python-2.0.
- Preserve actual package notices/attribution, not merely lock labels.
  Tool/dictionary licenses do not relicense program code or user exports.
- Hatchling runs as an isolated build backend. Complete assembled/transitive notices
  for uv, Node, managed CPython, Git and hosted Actions are not audited here.
  Redistributed Python needs PSF/bundled-library notices; other tools need their
  distribution notices. These binaries are not tracked or included in the application wheel.

## Fonts, graphics and recordings

| Material                                                    | Use / license boundary                                                                                                                                                                                        |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Windows Segoe UI, including bold                            | Loaded from Windows Fonts; no tracked fonts or font embedding in video. Raster output permission does not authorize copying fonts into an installer                                                           |
| Pillow fallback                                             | ImageFont embeds an Aileron Regular subset; publisher declares No Rights Reserved, permitting modification/redistribution. Preserve provenance and verify exact bundled font/native-library notices           |
| App icon                                                    | Drawn by project code in `ui/chrome.py`; no external icon asset                                                                                                                                               |
| Eleven Manta theme PNGs                                     | Generated references; CC BY-SA 4.0 with attribution/ShareAlike under the [image notice](docs/images/README.md)                                                                                                |
| workspace-dark.png, workspace-light.png, export-preview.png | CC BY-SA 4.0 under the same image notice, including scope/third-party limits                                                                                                                                  |
| Three README detail PNGs                                    | Outside that 14-image grant; see [detail captures](docs/images/README.md#readme-detail-captures)                                                                                                              |
| Five .forces recordings                                     | CC BY-SA 4.0 includes GPS/metadata; retain attribution/license/change notices and ShareAlike for adaptations; [catalog](docs/development/RECORDINGS.md) and [recording notice](tests/fixtures/real/README.md) |
| External Ride Forces / Apple Maps screenshots               | Not tracked; supplying screenshots does not authorize redistribution of third-party app/map imagery                                                                                                           |

- No tracked font files or external SVG/JPEG/icon assets. GPS uses no map tiles;
  no Apple Maps background is shipped. Product/park names grant no endorsement or trademarks.
- [Microsoft font FAQ](https://learn.microsoft.com/en-us/typography/fonts/font-faq):
  raster images/video and font redistribution are distinct.
- [Aileron publisher](https://dotcolon.net/fonts/aileron/): separate reuse statement,
  not permission to redistribute Segoe UI.

## Evidence and release limits

- Evidence: installed METADATA/RECORD/license texts, Node lock declarations, tracked
  assets, pinned encoder archive and encoder license/build output. This is not
  installer acceptance, security scanning or a complete embedded-library audit.
- Windows packages collect runtime notices, Python license, PyInstaller
  bootloader license/exception, static Qt notices and the redistribution catalog.
  The complete ZIP additionally contains FFmpeg publisher/license/build material.
- **Open:** Qt PDF/Chromium sources/notices and complete FFmpeg static-library
  corresponding sources/build instructions. [redistribution.json](packaging/redistribution.json)
  records these gaps; the builder reports them without blocking publication.
  This does not resolve or waive the obligations.
- Dependency source archives are verified as release-build inputs, not attached
  as a separate release download. [Package boundaries](docs/development/RELEASE.md#windows-packages)
  define checks/remaining limits; this inventory does not establish full release acceptance.
