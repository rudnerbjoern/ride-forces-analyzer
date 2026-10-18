# Localization verification

English/German contracts are defined in the
[localization guide](../development/LOCALIZATION.md).

## Verified scope

- Catalog coverage, matching placeholders and opaque source/user values.
- German numbers, unchanged sample clocks and preserved original diagnostics.
- Live UI switching without changing recording identity, curves, selection or zoom.
- Native Qt standard translations, light/dark and compact/scrollable layouts.
- Every dropdown choice fits the styled text field beside its arrow after
  repeated language switches, including 200% Windows scaling.
- All five overlay profiles in both aspects retain complete German glyphs and
  production-preview consistency. Overlay language persists independently in
  presets/jobs; older records default to English.
- Short German transparent/opaque landscape/portrait videos decode with the
  expected dimensions, fps, frame count and alpha.

## Scoped evidence

Native Windows x64, Python 3.14.6 / Qt 6.12.0 / FFmpeg 9.0.2;
`feat/4k-force-exports`, base `d88304e25dc67b9c0cec6ffe9c55f03d4d74e66b`,
plus localization and UI-sizing changes. Locked dependencies are unchanged.

Latest focused text-fit commands, from the repository root with native Python:

```text
python -m pytest tests/test_i18n_gui.py tests/test_theme_gui.py tests/test_export_gui.py tests/test_gui.py -q
python -m pytest tests/test_i18n.py::test_german_catalog_preserves_placeholders tests/test_i18n.py::test_declared_diagnostics_and_literal_ui_templates_have_translations tests/test_i18n.py::test_german_overlay_labels_fit_and_language_is_reproducible -q
```

Results: 21 GUI cases and 264 catalog/overlay cases passed. Ruff lint/format,
strict Pyright and mypy passed their changed-file scopes.
Native Node 26.5.0 handled scoped documentation/static checks; pinned Node
26.11.1 full-stack acceptance is not claimed.

UI language is session-only. Native dialogs and external errors may retain
system/original language; arbitrary-length user names are outside fixed-choice
text-fit guarantees. This is focused evidence, not a full application/hosted CI run.
