# Video export verification

<!-- cspell:words BGRA basetemp -->

[Export contracts](../implementation/VIDEO_EXPORT.md) define supported outputs
and the partial-M6 boundary.

## Verified scope

All five profiles support landscape 3840×2160 and portrait 2160×3840, signed forces,
missing tilt, smoothing and replay clocks. Exact-source-sample previews match
production frames independently of video fps. Theme graphics omit Hz/fps labels.
Vertical defaults positive-down/negative-up; lateral histories advance upward with
left/right deflection; longitudinal acceleration remains above zero and braking
below. No display direction changes source values.

G-Orbit uses a square circular-backed region with transparent corners. All force
tracks are 30 px wide: Vertical/Longitudinal outer radius 290 px, Lateral outer
radius 212 px with its inner edge preserved. Bold scales, white current bars,
signed readouts and the right 0–180° orientation semicircle fit both aspects and
languages. Missing orientation omits its marker. No direction hints, profile
name or replay footer are rendered.

Independent positive/negative peak envelopes hold for 1.5 source-time seconds,
release at 1 g/s, restart at new/repeated extremes and reset at gaps or selection
start. Fractional source positions and arbitrary query order are covered. Muted
peak bars and alpha-65 arc fills are checked against actual RGBA pixels, alongside
opaque current bars, background transparency and physical force directions.

Eight representative short encodes cover codec × aspect × CPU/GPU preference,
with all layouts represented. Codec, dimensions, fps, frame count, complete CPU
decode, alpha and opaque backgrounds are checked. Native assistant lifecycle,
language switching and controlled 4K-equivalent layouts retain focused coverage.
Original recordings and locked dependencies are unchanged.
Each layout now owns its renderer and region metadata in a separate built-in
module. Registry coverage checks every persisted profile, and a substituted custom
renderer verifies that placement/scaling does not depend on concrete layout classes.
The [layout API](../development/EXPORT_LAYOUTS.md) documents the extension contract.
Visual design constants are named and described at the start of each profile,
including independent portrait styling. Regression coverage checks individual
font/palette overrides without affecting other layouts, configurable peak timing
and rejection of invalid hold/release values. Default appearance remains unchanged.

## Local acceptance evidence

Native Windows x64, Python 3.14.6 / Qt 6.12.0 / FFmpeg 9.0.2;
`feat/export-theme-improvements`, base `661ff4cc84a234a4ca4302e4a88dc338eab24711`,
plus theme rendering, previews, assistant and reference/test/documentation changes.

```text
uv lock --check
uv run --locked ruff check .
uv run --locked ruff format --check src tests
uv run --locked mypy src
npm run typecheck
npm run test:types
npm run test:dependencies
node --test tests/ci/changes.test.mjs
uv run --locked pytest --basetemp=.tmp/delivery-pytest
npm run test:docs
```

Results on 2026-10-18: all 1,442 application tests passed in 213.95 s,
including per-layout style configuration and independent portrait settings.
Lock consistency, lint/format (91 files), mypy (58 source files), strict Pyright,
11 type-contract tests, 15 dependency-contract tests, 41 CI-routing tests and
documentation checks (65 link tests plus Markdown/spelling) passed.
The toolchain used uv 0.13.0 and pinned native Node 26.11.1.
Actual full-run output: `.tmp/delivery-full-check.log`.
Fourteen representative full-canvas RGBA frames matched the pre-refactor hashes
byte-for-byte, covering every layout, both aspects, English/transparent and
German/opaque output, with multiple G-Orbit source positions. All eleven reference
PNG hashes also matched after regeneration. Comparison evidence:
`.tmp/layout-constants-equivalence.log` and `.tmp/layout-baseline.json`.
The reference PNGs use fixed Manta sample 4782,
11-sample smoothing and the unchanged source hash; the final G-Orbit image was
visually inspected. Reference regeneration command:
`uv run --locked python scripts/render_export_reference.py`.
Temporary reference runner evidence: `.tmp/layout-constants-*.log`.

Local acceptance covers the complete application suite and the changed theme,
layout and documentation scope. It does not establish a new full-recording
render, physical 4K desktop inspection or hosted CI result. Actual long-recording
and editor compatibility remains scoped below.

## Full-recording compatibility evidence

The original four-panel landscape profile produced these complete 50 fps ProRes
4444 MOVs, each with complete CPU decode and unchanged source hashes:

| Recording      | Frames | Duration | File size           |
| -------------- | ------ | -------- | ------------------- |
| Manta          | 9,640  | 192.80 s | 5,749,011,991 bytes |
| Kraken         | 10,084 | 201.68 s | 6,430,961,650 bytes |
| Voltron Nevera | 10,504 | 210.08 s | 7,012,473,466 bytes |

Resolve 21.1.0.17 imported all three as ProRes 4444, Straight alpha, 3840×2160
at 50 fps with exact frame counts. Start/ride/end frame comparisons retain exact
alpha and maximum mean RGB error below 0.022/255.
This establishes actual media-pool import, not a visually inspected Onride
composite or full-recording validation of every profile/aspect/language.

## Size and editor limits

ProRes is an editing master and remains large. One 2 s Kraken segment measured
84,402,191 bytes as copied ProRes versus 36,258,030 bytes as FFV1 level 3 BGRA MKV
(about 57% less). Resolve imported the FFV1 clip and accepted Straight alpha;
actual FFV1 compositing is unverified. FFV1 is evaluated only, not an application
output or a whole-ride size guarantee.

The [Blackmagic Windows codec list](https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_19_Supported_Codec_List.pdf)
lists ProRes 4444 MOV decoding; [FFmpeg's ProRes options](https://www.ffmpeg.org/ffmpeg-codecs.html#ProRes)
define alpha precision. Automatic Onride synchronization, general physical
qualification and clean-machine release remain outside this export acceptance.

## Reproducible reference assets

`scripts/render_export_reference.py` fixes the authorized Manta hash, source sample
4782 and comparison settings; it never rediscovers the peak. Native Windows
`python scripts/render_export_reference.py --output .tmp/reference-rebuild`
reproduces all eleven existing PNGs byte-for-byte with the current renderer/fonts.
`python -m pytest tests/test_export_reference_script.py -q` verifies the fixed
sample/settings, cross-directory invocation, output geometry and changed-source
rejection. Two cases pass; changed-file Ruff/strict typing and documentation checks
pass. Actual output is retained in `.tmp/reference-script-*.log`. No encode or full
application suite is required for this script-only scope.
