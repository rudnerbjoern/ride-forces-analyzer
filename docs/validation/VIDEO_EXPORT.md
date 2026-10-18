# Video export verification

<!-- cspell:words BGRA -->

[Export contracts](../implementation/VIDEO_EXPORT.md) define supported outputs
and the partial-M6 boundary.

## Verified scope

All five profiles support landscape 3840×2160 and portrait 2160×3840, complete
geometry/labels, signed forces, missing tilt, smoothing and replay clocks.
Previews match production frames at the exact selected source sample, independently
of output fps. Both aspects persist in presets/jobs; mixed-aspect batches work.

Real short encodes cover five profiles × two aspects × transparent/opaque ×
CPU/GPU selection. FFprobe checks codec, dimensions, fps and frame count;
complete CPU decoding and pixel checks verify alpha, backgrounds and panels.
Cancellation/corrupt output cannot publish an incomplete file.
Original-byte preservation is checked for all five recordings.

Native scope: Windows x64, Python 3.14.6 / Qt 6.12.0 / FFmpeg 9.0.2,
NVIDIA RTX 4070 Ti (driver 617.14), Vulkan ProRes and NVENC H.264;
`feat/4k-force-exports`, base `d88304e25dc67b9c0cec6ffe9c55f03d4d74e66b`,
plus rendering/export UI/test changes. Locked dependencies are unchanged.

```text
python -m pytest tests/test_rendering.py tests/test_export_preview.py tests/test_export_gui.py tests/test_export_batches.py -q
```

The recorded aspect scope has 96 distinct passing cases. Changed-file Ruff,
mypy and strict Pyright passed. Native previews/review pages and decoded frames
were visually inspected. Scoped Node checks use 26.5.0; pinned 26.11.1 full-stack
or a current full application suite is not claimed.

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
