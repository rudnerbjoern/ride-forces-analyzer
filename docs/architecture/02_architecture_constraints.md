# 2. Architecture Constraints

[Architecture index](README.md)

## Technical constraints

- Native Windows is the validation and application target; Qt operation needs a
  desktop session. Python 3.14.6, uv and PySide6 are the current toolchain.
  Version pins and installation commands are authoritative in
  [project configuration](../../pyproject.toml) and [Windows setup](../development/SETUP.md).
- Use typed Python, Pydantic for bootstrap settings, Ruff, mypy, Pylance/Pyright
  and pytest. Node tools serve development/type/documentation checks only.
- Application processing must work offline. Installing dependencies and obtaining
  reference documentation can require network access.
- The importer supports only the explicitly dispatched schema 2.2.0. New versions
  require authorized evidence, an adapter and regression coverage.
- Importing and scientific processing stay outside Qt widgets. Frame generation
  and encoding remain separate responsibilities for implemented and future exports.

## Data and scientific constraints

All five owner-authorized recordings are read-only, including complete GPS data.
Never rewrite, normalize, redact or replace them during processing. Preserve
unknown JSON fields, original numeric spelling and exact bytes. The
[recording catalog](../development/RECORDINGS.md) owns the authorization/digest inventory.

Do not infer axis polarity, units, calibration, filtering, GPS sentinel meaning or
an epoch from successful parsing. The owner defaults rate 50 and riding position
Seated apply only to absence, with explicit provenance. Never fabricate gravity
or GPS. See [concepts](08_concepts.md) and [risks](11_technical_risks.md).

## Development constraints

[AGENTS.md](../../AGENTS.md) governs scope and Git authorization. Work on a feature
branch; integrate through an authorized PR, never a direct commit/push to main.
Finish milestone acceptance and documentation locally before publication; CI is
secondary validation. Temporary artifacts belong in `.tmp/`; source recordings
are excluded from text normalization. Dependencies are locked and reviewed.

Analysis uses locked NumPy/Pint/SciPy in the optional `analysis` extra.
GeographicLib is not adopted or required for the GPS reference-only scope.
AHRS and pyproj remain research only. Preserve actual binary/transitive
license notices for eventual distribution; see [ADR 0004](../decisions/0004-analysis-contracts-and-library-policy.md).
