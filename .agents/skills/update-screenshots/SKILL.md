---
name: update-screenshots
description: Refresh Ride Forces Analyzer reference screenshots and Stream Deck examples and verify their README and GitHub Pages presentation, captions and fixed reference settings using the existing native Windows generators.
---

# Update screenshots

Use the existing generators, not recreated charts or interface mockups. The Stream
Deck examples are labelled software illustrations rendered from production plugin
graphics, feedback and layout; they must never imply hardware verification. Run from
the repository root in a native Windows desktop session with the locked environment.
Read the [image reference guide](../../../docs/images/README.md) and
[README](../../../README.md) for the requested images and their current captions.

## Choose and refresh the images

When asked to refresh all reference images, run all five commands sequentially.
For a narrower request, run only the corresponding generator. Keep GUI capture
separate from other GUI tests or capture processes.

```powershell
# Full dark/light workspaces and export assistant; app-reference.json
uv run --locked python scripts/capture_app_reference.py

# Voltron airtime, Taron force cards, Manta smoothing; readme-reference.json
uv run --locked python scripts/capture_app_reference.py --details

# Appearance gallery; appearance-reference.json
uv run --locked python scripts/capture_app_reference.py --themes

# Five Voltron Nevera layouts, their detail crops and comparison sheet; voltron-reference.json
uv run --locked python scripts/render_export_reference.py

# Stream Deck +/Neo/Mobile user-guide illustrations; stream-deck-reference.json
uv run --locked python scripts/render_stream_deck_reference.py
```

The default destination is `docs/images`. To review first without replacing
tracked images, append `--output .tmp/screenshot-review` to the applicable command.
All commands can share that directory because their output names differ.
The Stream Deck generator needs the locked Node development dependencies. It
builds the existing plugin/profile artifacts and renders fixed control-contract examples; it never installs,
links or restarts the plugin, imports profiles, or connects to a device/Analyzer.

Preserve the fixed recordings, source hashes, sample indices, intervals, language
and settings defined by the generators and their manifests. Never search for a
new peak during a routine refresh. Source-hash mismatches require investigation;
do not bypass the guards or modify original `.forces` files. If a generator fails,
report which outputs were written and resolve the cause before presenting the
image set as refreshed. Do not use incomplete output as a reference.

## Review images and README embedding

- Open each changed image. Check readable labels, clipping, context strip/legend,
  transparency presentation and intended crop. The smoothing panels must retain
  identical time and force scales for windows 1, 11 and 31.
- Check local image links in the README and affected user guides: every intended
  refreshed image must be embedded in its owning feature description, and its path
  must exist. Verify
  filenames and letter case; do not embed temporary review paths.
- Compare captions and alt text with the generated manifests and actual images:
  recording, replay time, sample, smoothing, force values and visible context.
  Update descriptions in place when needed. Retain the existing links on coaster
  names and the distinction between provisional context and measured forces.
- Check the linked [layout gallery](../../../docs/user/EXPORT_LAYOUT_GALLERY.md) when its
  images change. Follow the [central image guide](../../../docs/images/README.md)
  for reproduction settings, licensing and attribution.
- For the Stream Deck examples, review the [user guide](../../../docs/user/STREAM_DECK.md):
  the README Playback close-up (`stream-deck-overview.png`) must match the Plus
  Playback panel and retain its software-illustration caption;
  native menu/function symbols, every Plus/Neo 2×4 profile page, aligned Plus touch fields/dials,
  the four Mobile 2×3 pages with Back and no Home, both Neo Touch Points,
  InfoBar state, visible state badges, readable/elided fields and the
  separate preview/applied marker values must match the generated manifest. Keep
  the software-illustration/example-value caption; leave physical acceptance open.
- Inspect the diff for unintended image/document changes. Preserve unrelated
  owner changes; do not stage, commit or publish as part of this skill.

## Check GitHub Pages presentation

The [Pages start page](../../../index.html) renders the README directly; do not
maintain a second copy of its content. Read the
[website setup](../../../docs/development/SETUP.md), section **Project website**, when reviewing
the [layout](../../../_layouts/default.html),
[stylesheet](../../../assets/css/style.scss) and
[Pages configuration](../../../_config.yml).

- Keep images under `docs/images` and verify their URLs resolve beneath the
  configured project base path. Preserve repository-relative image links in the
  README; its text links are adapted to GitHub by the Pages start page.
- Review the themed page at desktop and narrow widths when a rendered preview is
  available. Check screenshot legibility/aspect ratio, captions, horizontal
  overflow and navigation anchors after any README heading changes. Routine image
  refreshes do not require theme or download-button changes.
- Pages publishes from `main`, not the working branch. Local changes are pending
  until separately authorized delivery and a successful Pages build. Do not
  publish, change Pages settings or trigger a deployment as part of this skill.
- After an authorized deployment, verify the deployed revision/build and inspect
  the [published page](https://rudnerbjoern.github.io/ride-forces-analyzer/), including
  its refreshed images. Report local, rendered-preview and live-site results
  separately. If the deployed revision is older, or a preview/build is unavailable,
  mark that verification as open; an existing live page does not verify new images.

## Validate and report

Run `npm run test:docs` for Markdown, spelling and local link targets. This check
does not verify visual content, caption accuracy or a successful Jekyll/Pages
build; the reviews above are required where the relevant output is available.
If generator code changed, also run its affected focused tests:

```powershell
uv run --locked pytest tests/ui/test_reference_screenshots.py
uv run --locked pytest tests/rendering/test_reference_script.py
uv run --locked pytest plugins/stream-deck/tests/test_reference.py
```

Use only the relevant test file; unchanged generator code does not require a new
test run solely because images were regenerated. Report which image groups were
updated, the validation results and any remaining limits. Keep temporary logs in
`.tmp/`; do not add a historical validation report for a routine refresh.
