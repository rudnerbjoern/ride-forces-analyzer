# Portrait Safe Region implementation plan

Status: source research in step 1 is complete; the owner selected candidate B as
the HUD placement baseline below. Application steps 2–8 remain planned.
Reference case: Portrait HUD, 1080 × 1920.
Application implementation and Git delivery require their own authorization.

## Objective and scope

Add one optional **Safe Region** switch to Portrait video export. Off preserves
the existing layout. On adds moderate side clearance and can raise histories to
reduce edge cropping and the strongest lower-screen obstruction. Keeping the
onride view open takes priority over keeping every instrument outside platform UI.
Partial overlap is acceptable; complete containment in an unobstructed box is not
the product objective. Official risk areas inform placement without becoming
mandatory boundaries for all overlay content.

Target behavior:

- Default Off, including settings loaded without the new field.
- Support all four existing Portrait layouts: HUD, Flow Ribbon, Corner
  Instruments and G-Orbit. Four-panel column remains landscape-only.
- Keep each layout's current output resolution, 9:16 canvas, values, signs,
  time mapping, source range, language, transparency and encoding choices.
- Apply On to Full frame. Content area keeps its exact native-content contract;
  the switch is unavailable there and in Landscape. Switching to an unsupported
  combination makes the effective mode Off without rewriting saved records.
- Use one agreed placement profile behind the switch. Platform selectors,
  editable margins, video ingestion and automatic source-video cropping are
  outside this plan.

The Full-frame restriction is a proposed design decision. Candidate B is the
owner-selected HUD baseline for dependent implementation. Production rendering,
translations and the corresponding compact-layout arrangements still require
the verification in steps 3–4.

## Evidence and authoritative topics

Official references reviewed on 2026-11-14:

- [YouTube Shorts visual guides](https://support.google.com/youtube/answer/16215842?hl=en):
  identifies viewer controls/description areas and device-dependent unsafe edges
  for ordinary Shorts.
- [Google video-ad safe zones](https://support.google.com/google-ads/answer/13547298?hl=en-GB)
  and its [vertical PNG template](https://services.google.com/fh/files/misc/youtubesafezoneoverlay_vertical_final.png):
  the 1080 × 1920 advertising reference has margins of 48 px left, 192 px right,
  288 px top and 672 px bottom, defining an 840 × 960 rectangle. Its advertising
  scope must remain explicit when applying it to ordinary Shorts.
- [TikTok auction in-feed specifications](https://ads.tiktok.com/resources/help/article/tiktok-auction-in-feed-ads?lang=en)
  and [reservation in-feed safe-zone notes](https://ads.tiktok.com/resources/help/article/tiktok-reservation-in-feed-ads-reach-frequency?lang=en):
  templates vary with format, caption length and additional elements, including
  separate standard and anchor variants. Preview/live results can differ by device.

Step 1 records the measured source intersection and selected TikTok cases below
as research references. The intersection is not the target HUD footprint.
The seven owner-provided screenshots, `IMG_7319.PNG` through `IMG_7325.PNG` in
`.tmp/TikTok-and-Shorts/`, are local comparison evidence. They show both platform
obstruction and clipped edge content; they do not establish where cropping occurs.
Separate normal viewer UI from temporary cards and owner-only controls.

Use the existing [video export contract](VIDEO_EXPORT.md),
[preset/batch contract](EXPORT_BATCHES.md),
[layout API](../development/EXPORT_LAYOUTS.md),
[rendering boundary](../architecture/05_building_block_view.md#video-export-boundary)
and [snapshot concepts](../architecture/08_concepts.md#snapshot-lifetime-and-reuse).
This document owns the planned sequence and acceptance criteria. Implemented
behavior belongs in those authoritative topics when the feature is delivered.

## Implementation steps

Complete prerequisites in order. Each step has a concrete deliverable and a
separate verification condition; leave its boxes unchecked until both are met.
Reuse existing modules, fixtures and checks. No new dependency is planned.

### 1. Define the reference profile

Prerequisites: none.

- [x] Research: obtain and measure the official vertical TikTok LTR standard
  template and all four anchor/caption variants; normalize with Google's reference,
  derive a conservative shared rectangle and compare it with all seven screenshots.
- [x] Verify: cross-check labelled dimensions against raster boundaries, test
  normalization/containment, distinguish screen/video coordinates and inferred
  registration, and inspect the strict-containment study as a research reference.

Output: measured source definitions, researched on 2026-11-14, and candidate B as
the owner-selected moderate HUD baseline. Source measurements remain informative
references and do not prescribe production placement.

#### Source measurements and scope

Use top-left origin, x rightward and y downward. Rectangles below use half-open
`[left, top, right, bottom)` video coordinates; width is `right - left` and height
is `bottom - top`. Coordinates refer to the encoded video, not the phone screen.

Original downloads:

- Google: the linked vertical PNG is 1080 × 1920. Its fully transparent rectangle
  is exactly `[48, 288, 888, 1248)`; all 806,400 transparent pixels belong to it.
- [TikTok standard LTR archive](https://lf-tt4b.tiktokcdn.com/obj/i18nblog/tt4b_cms/en-US/5jqet0ab9qci-10e7f5Vig4uhAscNP8XPB0.zip):
  `In-Feed/Feed.png` is 2880 × 5120, showing a labelled 720 × 1280 canvas at 4×.
  The labelled reference scales by 1.5 to 1080 × 1920; raster coordinates scale
  by 0.375. Blue crop bands are 80 reference pixels at each side. Red UI bands
  reserve 160 at the top and 440 at the bottom. A 120-wide right UI column starts
  at y = 560, measured from the **inner** right edge x = 640: its left boundary
  is x = 520. The combined lower right exclusion is therefore 200 reference pixels
  from the outer edge, or 300 pixels after normalization.
- [TikTok anchor LTR archive](https://lf-tt4b.tiktokcdn.com/obj/i18nblog/tt4b_cms/en-US/5jqet0ab9qci-2ECwVwzIZXPqszI99UlWm3.zip):
  `1. Vertical Feed- 540x960/feed_1.png` through `feed_4.png` use a labelled
  540 × 960 canvas. Each actual PNG is 750 × 1334: use printed reference dimensions
  and a factor of 2 for normalization, not the raster width as the video width.
  The included instruction identifies one through four caption lines. Green
  boundaries agree with the labels within 1.1 reference pixels after accounting
  for rasterization. All variants reserve 126 at the top and 60 at the left.
  Their right boundary changes from x = 480 to x = 420 at y = 180; here the
  labelled right exclusion of 120 is measured from the **outer** edge x = 540.

The selected reference cases include ordinary LTR in-feed chrome and the depicted product
anchor, caption lengths 1–4, CTA and navigation layouts. Google and TikTok assets
are advertising references; their use for ordinary Shorts/feed videos is a
research scope, supported by the local screenshots, not a platform
promise. RTL, shopping/live panels, other interactive formats, expanded comments,
temporary rating/location cards and owner analytics/promotional controls are not
separately qualified cases.

| Reference                           | Normalized conservative rectangle | Bottom margin |
| ----------------------------------- | --------------------------------- | ------------- |
| Google vertical                     | `[48, 288, 888, 1248)`            | 672 px        |
| TikTok standard, below toolbar step | `[120, 240, 780, 1260)`           | 660 px        |
| TikTok anchor, 1 caption line       | `[120, 252, 840, 1108)`           | 812 px        |
| TikTok anchor, 2 caption lines      | `[120, 252, 840, 1042)`           | 878 px        |
| TikTok anchor, 3 caption lines      | `[120, 252, 840, 974)`            | 946 px        |
| TikTok anchor, 4 caption lines      | `[120, 252, 840, 906)`            | 1014 px       |

The TikTok rectangles deliberately extend the narrower lower toolbar boundary
upward to make each a single safe rectangle. Their upper safe areas are wider.
The anchor bottom exclusions in the labelled 540 × 960 reference are respectively
406, 439, 473 and 507 pixels; the right toolbar starts 780 pixels above the bottom.

Source SHA-256 fingerprints identify the measured artifacts:

- Google PNG: `56baf502e131f3fe79a61827363f4e262eaca41f094027896afb8a4c3a120717`.
- TikTok standard ZIP: `1bca1f5755b738ea809926f42b49fc59a24acca0dee40db7f978730d0c52ca53`.
- TikTok anchor ZIP: `d3796b32b4c974d1677b33e603627200b2024faf70eba50cf8e08b84bb112d45`.

#### Strict source intersection: reference only

Intersect the selected regions using maximum left/top and minimum right/bottom
bounds. The resulting strict reference is:

| Property                             | Reference value             |
| ------------------------------------ | --------------------------- |
| Canvas                               | 1080 × 1920 px              |
| Rectangle                            | `[120, 288, 780, 906)`      |
| Origin and size                      | x = 120, y = 288, 660 × 618 |
| Margins: left / top / right / bottom | 120 / 288 / 300 / 1014 px   |
| Additional project crop allowance    | 0 px                        |
| Share of complete canvas             | 19.67%                      |

At 2160 × 3840 the same normalized policy yields `[240, 576, 1560, 1812)`,
1320 × 1236 pixels. Scale coordinates from the reference rather than adding the
reference margins unchanged to higher-resolution canvases.

This rectangle describes full containment in the selected source masks. Using it
as the overlay's entire footprint would concentrate the instruments over a small
part of the onride picture; the requested feature instead retains the spread-out
HUD with moderate placement changes.

The original stepped masks also justify the reference rectangle. Their common
horizontal intervals are x = 120–888 for y = 288–360, x = 120–840 for
y = 360–840, and x = 120–780 for y = 840–906. The maximum-area single rectangle
is 660 × 618 = 407,880 px². The wider alternative, 720 × 552, has 397,440 px²;
the widest upper strip has only 768 × 72. No protected source area is relaxed.

For this strict reference calculation, no additional device-crop margin is added: the official 120-pixel left crop band
already exceeds the approximately 47–56 native pixels inferred in these examples.
This is a decision for the supplied evidence, not qualification of other devices.
The selected moderate baseline below uses extra side clearance independently of
this strict-containment calculation.

#### Screenshot comparison and assumptions

All seven original images are 1320 × 2868 phone screenshots. Their complete screen
includes status/navigation bars, so treating the screenshot itself as a 9:16 video
would produce incorrect coordinates.

For comparison only, fit a uniform scale `s` and translation `(tx, ty)` using
current Portrait HUD landmarks: history cursor x = 537.5, longitudinal axis
x = 970 and lateral axis y = 1435. The mappings are
`screen_x = s * video_x + tx` and `screen_y = s * video_y + ty`.
These are **inferred registrations**, assuming the pictured export uses the
current HUD geometry and uniform scaling. Original video metadata and uncropped
frames are unavailable; this does not identify the cropping stage or prove the
absence of additional transforms.

| Screenshot   | App            | Estimated scale | Approximate profile in screen pixels |
| ------------ | -------------- | --------------- | ------------------------------------ |
| IMG_7319.PNG | YouTube Shorts | 1.341           | `[96, 386, 981, 1215)`               |
| IMG_7320.PNG | YouTube Shorts | 1.339           | `[98, 389, 982, 1216)`               |
| IMG_7321.PNG | YouTube Shorts | 1.341           | `[96, 386, 981, 1215)`               |
| IMG_7322.PNG | TikTok         | 1.364           | `[88, 393, 988, 1236)`               |
| IMG_7323.PNG | TikTok         | 1.364           | `[88, 394, 988, 1237)`               |
| IMG_7324.PNG | TikTok         | 1.364           | `[88, 394, 988, 1237)`               |
| IMG_7325.PNG | TikTok         | 1.364           | `[88, 393, 988, 1236)`               |

An independent landmark check projects the unused left HUD axis x = 55 to
approximately screen x = 9–11 on YouTube, compared with the observed cyan column
at x = 10. On TikTok its projection is x = −1, consistent with clipping at x = 0.
The inferred horizontal loss is approximately 47–48 native pixels on each side
for YouTube and 56 for TikTok. Do not treat these rounded estimates as device specs.

The projected profile was visually checked in all seven screenshots: it stays
below the visible top controls/search bar, left of the right action column and
above the depicted caption, floating reaction and lower-card areas. Existing HUD
edge text and lower histories remain obstructed in the originals. This comparison
establishes the strict reference footprint in these static views, not a rendered-feature
or live-app acceptance result.

#### Compact containment study and source verification

The strict shared region is substantially smaller than the original HUD canvas.
The local synthetic containment study fits the existing font size classes inside
it, with measured ink bounds `[148, 316, 755, 867)`. Its containment checks passed.
That study is a geometric reference, not the intended production arrangement.
Production readability and all translated/data-extreme states remain step 4 work.

Reference-boundary, normalization and six-source rectangle-containment assertions
passed on native Windows. Google alpha bounds and TikTok color-band boundaries
were measured directly; anchor raster boundaries were cross-checked against the
printed coordinates. All four caption cases and all seven screenshot registrations
were inspected. Research artifacts remain under `.tmp/safe-region-research/`:
the original downloads, `measurements.json`, `screenshot-comparison.jpg`,
`hud-safe-region-proposal.png`, `hud-proposal-detail.png` and the reproducible
measurement/visualization scripts. No downloaded image is a published fixture.

#### Selected moderate placement: candidate B

The local candidates in `.tmp/safe-region-review/` use the existing HUD renderer
with temporary in-memory geometry edits. They share the hash-guarded Voltron
Nevera reference sample 8575 and the bundled Toutatis preview photo. The photo is
an illustrative background, not footage synchronized with the measurement.
All use the original 1080 × 1920 canvas, fonts, values and 96-pixel history rows.
Application files, source recordings and saved export settings are not changed.

| Candidate | Additional side inset | History/lateral lift | History top |
| --------- | --------------------- | -------------------- | ----------- |
| Existing  | 0 px                  | 0 px                 | 1535 px     |
| A: light  | 72 px per side        | 80 px                | 1455 px     |
| B: medium | 72 px per side        | 160 px               | 1375 px     |
| C: higher | 72 px per side        | 240 px               | 1295 px     |

For A–C, heading/value anchors move from a 40-pixel to a 112-pixel edge inset.
The side scales, history labels/plots, lateral endpoints and orientation strip
move coherently inward. Shortening the side scales at their lower end preserves
clearance above the raised lateral instrument. The center remains transparent;
there is no new opaque panel or compact full-containment box.

`comparison-pov.jpg` compares the four arrangements on the same POV background.
`comparison-phone.jpg` adds schematic platform controls and the same inferred
TikTok screenshot crop to each candidate. Controls are illustrative, not actual
platform screenshots or a claim that all UI variants are covered. Full-resolution
`off`, `a`, `b` and `c` POV/phone images and a parameter manifest accompany them.

The owner selected **B: medium** as the starting point: 72 additional pixels of
side inset per side and a 160-pixel upward shift of histories and the lateral
instrument. The existing arrangement and A/C remain comparison alternatives.
Some controls/captions may still cover the HUD; preserving the open central
onride view takes priority over full containment.

For the 1080 × 1920 HUD reference, B fixes these baseline values:

- Heading/current-value edge inset: 112 px; history-heading x: 112 px.
- Side axes: x = 127 / 898; scale top/bottom: y = 440 / 1035.
- Lateral scale: y = 1275, x = 202–873; zero axis: x = 537.5.
- History block: y = 1375, left x = 167, row height 96 px; time cursor x = 537.5.
- Orientation strip: additional 72-pixel inward offset.
- Canvas, fonts, values, time context and upper heading/value baselines retain
  the existing reference settings.

These are the reviewed preview parameters, not evidence of an implemented
application setting. Verify their production behavior in steps 3–4; the compact
layouts need their corresponding arrangements there. Preserve the source
measurements above as reference information.

### 2. Add the typed setting and compatibility rules

Prerequisite: step 1, with owner-selected candidate B as the HUD baseline.

- [ ] Implement: extend `rendering.model.ExportSettings` using the existing typed
  settings conventions. Represent Off and the agreed profile with stable stored
  values, for example `off` and `portrait_social_v1`; the UI remains a single
  switch. Keep a profile identifier immutable so later platform changes cannot
  silently redefine a saved job. Validate Portrait/Full-frame eligibility outside
  Qt widgets. Runtime processing uses local geometry and requires no network.
- [ ] Verify: omitted values load as Off; valid modes round-trip; unknown modes,
  wrong types and explicitly unsupported combinations fail validation. Existing
  settings retain their dimensions and effective defaults.

Output: tested model/serialization contract, with English inline documentation.

### 3. Resolve shared geometry

Prerequisite: step 2.

- [ ] Implement: extend the existing layout geometry path in
  `rendering/layouts/contracts.py` and `registry.py` as needed. Scale the agreed
  additional insets/offsets to the actual canvas, including 2160 × 3840 compact
  layouts. Retain the selected supported edge/corner and the spread-out layout;
  do not fit the whole overlay into the strict source intersection.
  Keep geometry and eligibility logic independent of widgets and encoders.
- [ ] Verify: test canvas/crop clearance, offsets and supported positions
  at both native canvas sizes. Off resolves to the existing geometry exactly.
  Content-area dimensions and Landscape placement remain unchanged.

Output: one geometry source used by preview, frame composition and encoding.

### 4. Adapt the four Portrait layouts

Prerequisite: step 3.

- [ ] Implement: give HUD a Safe Region arrangement that moves side instruments
  inward and histories upward, with coherent spacing for current values, context,
  lateral scale and optional orientation marks. Give Ribbon, Corners and G-Orbit
  corresponding moderate edge clearance while preserving their layout character.
  Preserve readable typography, aligned optical axes and an open central view.
- [ ] Verify: render all four layouts in EN/DE/FR using existing authorized
  fixtures. Check labels, signed values, endpoints, missing-channel states and
  optional orientation marks against the agreed insets and actual canvas. Inspect related elements
  together for baseline, spacing, overlap and legibility. Compare Off with existing
  rendering references; scientific values/scales/time semantics must agree.
  Assess remaining UI overlap and central-view obstruction together, without
  requiring complete protection from all platform overlays.

Output: readable production renderings for both modes of every Portrait layout.

### 5. Persist the complete export choice

Prerequisite: step 2; use final geometry from steps 3–4 for integration checks.

- [ ] Implement: carry the setting through presets, immutable batch jobs,
  `ExportSnapshot`, embedded video metadata and export-history repeat. Use the
  existing JSON/model storage path; add a database migration only if the actual
  storage representation requires one. Saved jobs retain their captured profile
  when presets or current UI settings change.
- [ ] Verify: cover legacy records without the field, explicit On/Off saves,
  reload/restart, preset replacement/deletion, mixed-mode batches and repeat export.
  Reading legacy data must not rewrite it. Unknown profile identifiers must not
  silently fall back to a different layout.

Output: reproducible saved and repeated exports using the selected mode.

### 6. Integrate the switch and preview guidance

Prerequisites: steps 3–5.

- [ ] Implement: add the switch near aspect/area/position in `ui/exports/form.py`.
  Show its effective state in review and relevant preset/batch summaries. Add
  EN/DE/FR labels and a short explanation of protection limits. Refresh the main
  preview and layout thumbnails through the existing debounced worker. When On,
  show the adjusted HUD directly. Any sourced risk guidance stays subtle and
  preview-only, without obscuring the POV or implying full protection.
- [ ] Verify: exercise On/Off, layout/aspect/extent changes, saved-setting loads
  and rapid changes without stale preview results. Check keyboard/accessibility
  labeling, translated text, alignment and smaller/high-DPI windows together in
  one reusable native Windows application session. Guides must not alter the
  production frame image or appear in encoded output.

Output: one consistent user control and an accurate, clearly marked preview.

### 7. Verify single and batch video output

Prerequisites: steps 4–6.

- [ ] Implement: connect the effective geometry to the existing frame and encoder
  paths, accounting for their region placement/padding behavior. Ensure transparent
  MOV and opaque MP4 use the same arrangement, and that batch preparation captures
  the same settings as single export. Keep analysis preparation independent of
  this display-only choice.
- [ ] Verify: use focused rendering/metadata tests plus short representative
  transparent and opaque encodes. Confirm dimensions, placement, alpha/opaque
  behavior, snapshot mode and absence of preview guides in decoded frames.
  Compare preview and exported frames at the same source position. Verify serial
  and parallel rendering agree; compare screenshot obstruction/crop masks with
  the new arrangement, recording any remaining overlap explicitly.

Output: verified output parity across individual, batch and repeated exports.

### 8. Update authoritative documentation and finish acceptance

Prerequisite: steps 1–7.

- [ ] Implement: update the existing video-export and preset/batch contracts,
  layout API and affected user export/layout/preset guides. Explain the control,
  eligibility, retained output dimensions and limits. Refresh only directly
  affected examples/reference settings through the existing screenshot workflow.
  Replace planned descriptions with the final contract and mark completed steps
  here without adding an execution diary.
- [ ] Verify: follow the documentation-maintenance workflow, including independent
  semantic review for substantive user-facing changes. Run affected rendering,
  storage/history, UI and encoding regressions plus configured lint/type and
  documentation checks. Start focused; broaden only for concrete change impact.
  Reuse application sessions and unchanged passing evidence. Keep runner logs in
  `.tmp/` and report results/limits concisely; this plan requires no separate
  routine validation report, release or additional package-build matrix.

Output: documentation matching the delivered feature and verified acceptance.

## Completion criteria

- [ ] Every implementation step and its verification condition above is complete.
- [ ] Off preserves existing output; On uses the owner-agreed moderate placement
  for every eligible Portrait layout, with readable labels in all three languages
  and an open central onride view. Partial platform overlap remains acceptable.
- [ ] Preview, encoded output, presets, jobs, metadata and repeat export agree.
- [ ] Known limits remain explicit: expanded comments, temporary rating/location
  cards, owner controls and changing device/app behavior can still cover content.
- [ ] The owner can choose either the existing arrangement or the protected one
  through the single switch, without changing the output canvas or recording data.
