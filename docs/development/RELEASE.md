# First public release preparation

## Intended scope

Prepare `v0.1.0` as a **GitHub prerelease distributed as source**, matching
`project.version` in [pyproject.toml](../../pyproject.toml). This is a proposed
release, not a published version or a completed acceptance claim.
The source checkout uses the documented Windows setup; it is not a standalone
installer. Do not bundle `.venv`, Node tools, FFmpeg, fonts, local databases,
exports or `.tmp/` contents as release assets.

GitHub's source archives should reference the approved release commit. They
include the five authorized full recordings with GPS and metadata and the
separately licensed documentation images. Their original bytes must remain intact.
Binary distribution and its additional third-party notice/source obligations
remain outside this first source release; see [third-party notices](../../THIRD_PARTY_NOTICES.md).

## Release description draft

The following text is prepared for the GitHub release description:

---

**Ride Forces Analyzer 0.1.0 — Windows source preview**

Explore recordings from the Ride Forces mobile app and create G-force overlays
for your coaster videos. Processing stays on your computer and preserves original
recordings.

- Interactive vertical, lateral and longitudinal force charts, smoothing,
  sample inspection and selected-range extrema.
- Approximate GPS overview and available ride, device and weather metadata.
- Five overlay layouts with landscape/portrait previews, transparent ProRes 4444
  or opaque H.264 export, plus optional NVIDIA acceleration when supported.
- Saved export presets and batch definitions in a local SQLite database.
- English/German interface and light/dark appearance.

**Install:** download and extract the source archive, open PowerShell in its
folder, then run `setup.ps1` and `start.ps1`. Video export additionally needs
`setup.ps1 -VideoExport` or an existing compatible `ffmpeg.exe`.
Initial setup downloads dependencies; installed processing works offline.
Windows x64 is the supported target; no standalone installer is supplied.
See the [README](../../README.md#get-started) for instructions and screenshots.

**Preview limitations:** calibrated forces require usable source calibration
directions. Source-app agreement has recording-specific limits; GPS provides rough
context rather than force or speed measurement. Persistent ride-library management,
interactive playback and video synchronization are not implemented. Exports need
manual alignment with footage. See the [roadmap](../ROADMAP.md).

Program code: GPL-3.0-or-later. The five included recordings with GPS/metadata and
the listed documentation images: CC BY-SA 4.0, with their attribution notices.
These licenses do not automatically apply to your recordings or exports.
Report bugs through the issue templates and security problems privately via
[SECURITY.md](../../SECURITY.md).

---

Use repository URLs pinned to the release tag when copying the description to
GitHub; the relative links above are for this document's location.

## Publication gates

The release remains pending until all of the following are verified:

- The owner approves the release scope, version and public repository visibility.
- Pending changes are reviewed and integrated through an explicitly authorized PR;
  required hosted checks pass for its reviewed revision.
- All applicable [local Windows checks](SETUP.md#required-project-checks) pass for
  the final release content. Full-suite execution needs renewed owner approval;
  documentation checks alone do not qualify the application for release.
- A fresh extraction of the intended source archive passes setup, application
  startup, fixture import, GPS overview, export preview and a short CPU video
  export on native Windows. Verify both languages and light/dark appearance;
  record the tested environment and remaining clean-machine limits.
- Source archives retain licenses, attribution, locked dependencies and original
  fixture bytes. Apply the [publication review](../../SECURITY.md#publication-boundary)
  to the intended files/history and any hosted assets; earlier findings do not
  certify later additions.
- The owner separately authorizes tag creation, release publication and any
  visibility change. Publish the approved commit as a prerelease; do not silently
  substitute a newer branch tip or claim installer support.

Keep runner logs under `.tmp/` and final release validation concise and specific
to the tested content. Hosted outcomes belong in the PR/release metadata.
