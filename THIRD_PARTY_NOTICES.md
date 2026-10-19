# Third-party licenses and materials

<!-- cspell:words shiboken ast flexcache flexparser librt iniconfig pluggy dateutil tzdata libx264 libx265 nonfree Aileron GyanD WTFPL CMU QtCharts buildconf Segoe -->

Project copyright © 2026 Björn Rudner. The program code is
[GPL-3.0-or-later](LICENSE). External components retain their
own licenses. This inventory identifies notice/source duties; it is not a complete
notice bundle or clearance for a future installer. Versions/hashes remain in
[uv.lock](uv.lock), [package-lock.json](package-lock.json) and [ffmpeg.json](ffmpeg.json).

## Python application components

The inspected Windows environment contains 36 third-party distributions plus this
project. Top-level declarations do not replace bundled-component notices.

| Component                                                   | Observed license                                                           | Handling when redistributed                                                                                 |
| :---------------------------------------------------------- | :------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------- |
| PySide6, Essentials, Addons, Pdf, WebEngine; shiboken6      | Metadata: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; Qt modules differ | Preserve binding, Qt and third-party notices; satisfy the actual selected module licenses                   |
| Qt Core, Gui, Widgets                                       | Qt LGPLv3/GPLv3 options                                                    | Retain terms, source access and replacement/reverse-engineering rights when using LGPL                      |
| **Qt Charts**                                               | **GPLv3 or commercial**, not general LGPL                                  | Application imports QtCharts; the GPL route requires corresponding source for a distributed combined binary |
| pydantic, pydantic_core, annotated-types, typing-inspection | MIT                                                                        | Retain copyright and permission notices                                                                     |
| typing_extensions                                           | PSF-2.0                                                                    | Retain license and notices                                                                                  |
| NumPy                                                       | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 in metadata             | Retain the complete wheel license collection and native-component notices                                   |
| SciPy, Pandas, Pint, flexcache, flexparser                  | BSD-3-Clause in inspected texts                                            | Retain copyright, conditions and disclaimers; no endorsement using contributor names                        |
| pyqtgraph, six                                              | MIT                                                                        | Retain supplied notices, including bundled material                                                         |
| Pillow                                                      | MIT-CMU plus bundled component licenses                                    | Retain the full installed LICENSE, not only the top-level grant                                             |
| python-dateutil                                             | Apache-2.0 / BSD notices                                                   | Retain the supplied combined license text and attribution                                                   |
| tzdata                                                      | Apache-2.0; bundled time-zone data has a separate public-domain notice     | Retain both installed notice files                                                                          |

[Qt licensing](https://doc.qt.io/qt-6/licensing.html) and the
[Qt Charts license](https://doc.qt.io/qt-6/qtcharts-index.html#licenses) distinguish
module terms. The project's or-later grant does not relicense GPL-3.0-only
dependencies or guarantee that the combined application can select a future GPL
version while retaining the same dependencies.

Installed PySide6 metadata does not supply the full Qt notice collection.
[QT-NOTICES.txt](packaging/QT-NOTICES.txt) supplies original license and attribution
texts from the official Qt/PySide 6.12.0 source archives for the relevant modules.
The existing packager includes that text in the EXE and both ZIPs. The source
archives are pinned in `packaging/redistribution.json` for source delivery.
Qt PDF/Chromium is not covered by those archives: PyInstaller collects a PDF
plugin even without a direct application import. Its sources/notices remain open.

NumPy has 20 license-related files. SciPy's main notice covers OpenBLAS, LAPACK
and GCC runtime components, including
`GPL-3.0-or-later WITH GCC-exception-3.1`; retain the exception. Do not describe all
numerical binaries as merely BSD. Pillow's installed notice includes image,
compression and font libraries such as FreeType; retain the complete notice and
required credits under the licensing route used by the actual binary.

## FFmpeg build

Setup downloads GyanD's **9.0.2 full static Windows build** from the
[pinned release](https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2).
The local archive matches SHA-256
`f0e46253c70dfe902bac915dfb4224f0cf1b7c6eeab9da2ccc9a5581f9a71b13`.
The installed ffmpeg.exe matches the extracted encoder byte-for-byte by SHA-256.
The encoder reports **GPL version 3 or later** through `-L`.
`-buildconf` includes `--enable-gpl`, `--enable-version3`, `--enable-static`,
`--enable-libx264` and `--enable-libx265`, without `--enable-nonfree`.
This is not an LGPL-only build.

The archive contains LICENSE and README.txt; its README names source commit
`946fcce07b`. This upstream reference is not a verified complete corresponding-source
bundle for all statically linked libraries. The local extracted encoder directory
currently lacks the archive's LICENSE/README; this audit does not repair downloads.

The program invokes a separate executable; application code links no FFmpeg DLL.
Neither encoder nor archive is tracked. Setup downloads from the publisher, or
users select their own encoder. An installer that bundles FFmpeg must retain its
license/readme, inventory every linked library and provide corresponding source,
build information and notices for the exact binary. A generic source URL alone
does not establish compliance. [FFmpeg legal guidance](https://www.ffmpeg.org/legal.html)
explains build-dependent licensing. Codec patent permissions are separate;
this inventory does not establish patent clearance.

## Development and build tools

These are not application imports. Preserve their terms when redistributing a
development environment rather than only project source.

PyInstaller 6.22.3 is an optional locked build-group tool (GPLv2-or-later with its
special distribution/bootloader exception). Its full COPYING text is collected
in Windows candidates. It does not change the project's GPL-3.0-or-later grant.

| Installed Python tools                                                                                | Observed license                                                    |
| :---------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------ |
| ast_serialize, librt, mypy, mypy_extensions, iniconfig, platformdirs, pluggy, pytest, pytest-qt, ruff | MIT; retain additional bundled notices, especially mypy             |
| colorama                                                                                              | BSD-3-Clause                                                        |
| Pygments                                                                                              | BSD-2-Clause                                                        |
| packaging                                                                                             | Apache-2.0 OR BSD-2-Clause                                          |
| pathspec                                                                                              | MPL-2.0; preserve notices and source availability for covered files |

All 196 non-root Node lock entries declare a license: 183 MIT, six ISC, two
BSD-2-Clause, one BSD-3-Clause, one WTFPL, one CC BY-SA 4.0, one PSF-2.0 and one
Python-2.0. These are lock entries, not unique upstream projects.
`@cspell/dict-en-common-misspellings` is CC BY-SA 4.0: retain attribution/license,
mark changes and respect share-alike for adaptations. `@cspell/dict-django` declares
WTFPL. The two argparse entries declare PSF-2.0 and Python-2.0. Tooling/dictionary
licenses do not relicense program code or user exports. Preserve actual package
texts/attribution when redistributing tools; lock labels are not notice texts.

Hatchling is an isolated build backend, outside the 36 installed distributions.
uv, Node, managed CPython, Git and hosted Actions are external tools/services;
their complete assembled/transitive notices were not audited here. Shipping a
Python runtime requires its PSF and bundled-library notices; shipping other tools
requires their actual distribution notices. No such binaries are tracked or
included by the current application wheel.

## Fonts, graphics and recordings

| Material                                                      | Verified use and remaining boundary                                                                                                                                                                                                |
| :------------------------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Windows Segoe UI, including bold                              | Loaded from the user's Windows Fonts directory; no tracked font files or font embedding in video. Raster output is permitted; copying fonts into an installer is not thereby authorized                                            |
| Pillow fallback                                               | Installed ImageFont embeds an Aileron Regular subset; the font publisher declares No Rights Reserved and permits redistribution/modification. Preserve provenance and verify exact bundled font/native-library notices for release |
| App icon                                                      | Drawn by project code in `ui/chrome.py`; no external icon asset found                                                                                                                                                              |
| Eleven Manta theme PNGs                                       | Generated by the fixed-sample reference script; licensed under CC BY-SA 4.0, with attribution and ShareAlike. See docs/images/README.md                                                                                            |
| workspace-dark.png, workspace-light.png, export-preview.png   | Project application screenshots, licensed under CC BY-SA 4.0. See docs/images/README.md for attribution, scope and third-party rights                                                                                              |
| Five .forces recordings                                       | CC BY-SA 4.0 covers all five originals including GPS/metadata; retain attribution, license and change notices, and ShareAlike for shared adaptations. See the recording catalog                                                    |
| Ride Forces / Apple Maps screenshots supplied in conversation | Not tracked as repository image files; supplying them does not establish permission to redistribute third-party app/map imagery                                                                                                    |

The tracked asset inventory has 14 PNGs, no font files and no external SVG/JPEG/icon
files. GPS draws positions without map tiles; no Apple Maps background is shipped.
Product/park names do not imply endorsement or grant trademark rights.
The [Microsoft font FAQ](https://learn.microsoft.com/en-us/typography/fonts/font-faq)
distinguishes raster image/video output from font redistribution.
The [Aileron publisher](https://dotcolon.net/fonts/aileron/) provides the font's
separate reuse statement; it is not a Windows Segoe UI redistribution permission.

## Evidence and release limits

The inventory covers installed METADATA/RECORD/license texts, Node lock declarations,
tracked assets, the pinned encoder archive and actual encoder license/build output.
Version 0.3.1 retains the locked runtime versions. The
[Windows package guide](docs/development/RELEASE.md#windows-packages) defines
package checks and their verification limits.
The five supplied recordings and 14 documentation PNGs
are CC BY-SA 4.0 under their separate attribution/scope notices. This is
not installer acceptance, a security scan or a complete embedded-library audit.

The Windows builder collects installed runtime notice files, the Python
license and the PyInstaller bootloader license/exception into each package.
The complete package additionally retains the exact pinned FFmpeg publisher's
LICENSE/README and executable build information, plus the static Qt notice text.
Qt PDF/Chromium and FFmpeg's complete static-library corresponding sources remain
open; generic upstream links do not supply the missing corresponding sources.
`packaging/redistribution.json` records these gaps and is shipped with the binaries;
the package builder reports them without blocking publication. This does not
resolve or waive the external license/source obligations;
see [package boundaries](docs/development/RELEASE.md#windows-packages).
