# Localization

For changing application language and appearance, see the
[user explorer guide](../user/EXPLORER.md#adjust-smoothing-and-display).

The application supports English, German and French offline.
Language choices are saved in local `preferences.sqlite3`. Without a valid saved
choice, the preferred OS display language selects its registered language, including
regional variants such as fr-CA; unsupported primary languages fall back to English.
An explicit `AppSettings(language=Language.GERMAN)` overrides the saved language for
startup; subsequent Settings choices are saved. Save applies language changes;
Cancel retains the active choice. Preference validation and storage fallbacks belong
to the [runtime contracts](CODE_QUALITY.md#runtime-and-static-contracts).
Appearance and adaptive widget behavior belong to the
[Explorer contract](../implementation/RAW_EXPLORER.md) and
[export assistant contract](../implementation/VIDEO_EXPORT.md#assistant-and-previews).

## Text ownership

The `i18n` package groups translation logic and catalogs. `i18n/__init__.py`
retains the shared public imports, including `Language` and `tr`; the Qt-specific
bindings remain in `ui.presentation.translation`.

- `i18n.Language` is a `StrEnum` with `ENGLISH`, `GERMAN` and `FRENCH` members.
  Python APIs use enum members; `Language(code)` converts a supported text code
  and rejects unknown codes. SQLite preferences and JSON presets retain the
  existing `en`, `de` and `fr` values. `LANGUAGES` registers their native
  names, locales, number separators, application catalogs and diagnostic catalogs.
  Settings, OS-language matching, storage validation and export selectors use this
  shared registration; selector indices preserve English, German, French order.
- English templates are stable keys. German uses `i18n/de.py`; French uses
  `i18n/fr.py`. Entries use concise labels and matching positional
  placeholders. `i18n.tr` separates text
  from opaque values, so recording names, paths and preset/batch names are never
  translated or interpreted as format strings.
- CSpell checks `i18n/de.py` with English/German and `i18n/fr.py`
  with English/French using locked dictionaries. Legitimate technical compounds
  are scoped to their catalog file. Catalog tests
  check completeness and placeholders independently of spelling.
- German numeric formatting uses decimal commas and grouping dots; French uses
  decimal commas and narrow non-breaking grouping spaces (U+202F). Source numeric
  tokens, units and `MM:SS.ff` sample counters are not localized or parsed again.
- Chart labels and tooltips use Start/End/Gravity/Incline marker names rather than
  JSON field names. German uses Start-/End-/Schwerkraft-/Neigungsmarkierung;
  menu actions and calibration explanations use Schwerkraft and Neigung consistently.
- `ui.presentation.translation` binds Qt text properties, combo entries and table headers.
  Language changes update these bindings and the explorer's dynamic presentation,
  preserving data identity, smoothing, cursor, selections and viewport.
  The installed Qt catalog for the selected language supplies standard Qt
  dialog/button text.
- Diagnostic codes, JSON paths and original diagnostic objects/messages remain
  unchanged. Each translated catalog provides code-specific explanations; the original
  technical text is explicitly selectable. Native OS dialogs follow platform
  rules; external encoder/runtime details may remain in their original language.
- Export settings store a separate `language` field. New assistants initially use
  the UI language, while loaded presets restore their saved choice. Rendering,
  previews and batch snapshots use that explicit language. Stored required fields and optional defaults follow the
  [preset/job contract](../implementation/EXPORT_BATCHES.md#contracts). UI switching
  never changes an existing saved job.

## Maintaining translations

Use `tr("Template {0}", value)` for application text, with complete sentences and
matching placeholders. Bind widget text through the existing Qt helper; do not
translate source identifiers, object names, enum keys, filenames or user content.
Keep every registered translated catalog complete and preserve English fallback.
Keep German and French catalogs in the same feature sections and key order, with
English comments identifying each section. Sort English keys alphabetically within
each section. Remove obsolete keys only after checking literal and dynamic uses,
including model labels, status values and translated exception messages.
Rendering must pass
the language from ExportSettings rather than read the current UI locale.

To add a language, extend `Language`, provide its application/diagnostic catalogs
and register one `LanguageDefinition`. No additional language-specific selector or
storage branches are required. Add locale, persistence and representative UI/export
checks. Catalog tests check all entries together per language, including keys and
placeholders. This lightweight catalog does not provide general plural-rule or
context-disambiguation tooling; use complete explicit singular/plural templates.

Add regression coverage for placeholder compatibility, source preservation and
new visible behavior. Inspect localized layouts on native Windows, including compact
windows and both export aspects. Production glyph bounds, preview consistency,
explicit saved-language round trips and representative real encodes are covered
by the localization and rendering regression suites.
