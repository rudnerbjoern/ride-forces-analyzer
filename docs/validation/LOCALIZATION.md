# Localization verification

English/German contracts are defined in the
[localization guide](../development/LOCALIZATION.md).

## Verified scope

- Catalog coverage, matching placeholders and opaque source/user values.
- German numbers, unchanged sample clocks and preserved original diagnostics.
- Live UI switching without changing recording identity, curves, selection or zoom.
- Native Qt standard translations, light/dark and compact/scrollable layouts.
- Every dropdown choice fits the styled text field beside its arrow after
  repeated language switches. Export layouts use 4K-equivalent working areas
  at 150% and 200% scaling, with visible settings and pinned actions. A compact
  fallback checks scrolling separately.
- All five overlay profiles in both aspects retain complete German glyphs and
  production-preview consistency. Overlay language persists independently in
  presets/jobs; older records default to English.
- Representative German encodes belong to the main encoder matrix; complete
  language/layout/aspect glyph coverage is checked directly without encoding.

## Scoped evidence

Native Windows x64, Python 3.14.6 / Qt 6.12.0;
`feat/4k-force-exports`, HEAD `fc759bb2c94a4fbf254eaa84d59e9f28bfd4424c`,
plus working-copy test changes. Locked dependencies are unchanged.

Latest focused text-fit commands, from the repository root with native Python:

```text
uv run --locked pytest tests/test_i18n_gui.py tests/test_gui.py tests/test_explorer_gui.py tests/test_export_gui.py tests/test_theme_gui.py -q
uv run --locked pytest tests/test_i18n_gui.py -q
```

Results: 57 GUI cases passed; the final localization-only run passed all 6 cases,
including the compact fallback in the 200% case. Ruff lint/format and strict Pyright pass the three
changed GUI test files. Logs: `.tmp/4k-workspace-*.log`.

The 4K cases control Qt client dimensions on the installed Windows desktop; they
do not change monitor resolution or claim physical 4K visual acceptance. Startup
checks separately honor the actual desktop limits. No full-suite or hosted CI
result is claimed for these changes.

UI language is session-only. Native dialogs and external errors may retain
system/original language; arbitrary-length user names are outside fixed-choice
text-fit guarantees. This is focused evidence, not a full application/hosted CI run.
