# Contributing

Small, focused contributions are welcome. Use an issue to discuss substantial
features before implementation; report vulnerabilities through
[SECURITY.md](SECURITY.md), not a public issue.

## Set up and verify

Use native Windows and the versions pinned in the repository. Install the
matching Node version, then run PowerShell from the repository root:

```powershell
.\setup.ps1 -Development
.\start.ps1
```

For video-export work, also run `.\setup.ps1 -VideoExport`.
The [setup guide](docs/development/SETUP.md) owns tool versions, troubleshooting
and the complete required check commands. Use locked dependencies; do not install
ad hoc packages into the environment.

Start with focused tests for changed behavior and add regression coverage for
bug fixes. Before submitting, run all applicable checks from the setup guide;
do not substitute non-Windows results for Windows/GUI validation. Run separate
delivery-skill tests only when their relevant implementation or inputs change.
For documentation-only changes, run `npm run test:docs`.

## Pull requests

- Create a dedicated branch from current `main` and keep changes scoped.
- Explain the problem, resulting behavior, actual check commands/results and
  remaining limits in the PR template. Use a draft while work is incomplete.
- Follow the [commit format](.github/commit-message-instructions.md). Write code,
  documentation and commit messages in English; maintain English/German UI text
  and layout fit when changing user-facing behavior.
- Match the existing [architecture](docs/architecture/README.md); keep import,
  analysis, storage and rendering logic outside Qt widgets.
- Update current behavior/limits in existing documentation. Avoid development
  diaries, unrelated refactors or weakening checks. Keep temporary artifacts in
  `.tmp/`; never commit environments, exports, credentials or private logs.

CI must pass before merge. Maintainers review and merge contributions.
Coding agents must also follow [AGENTS.md](AGENTS.md), including the owner's
separate authorization requirements for Git operations.

## Recordings and licenses

Every original `.forces` fixture is read-only. Preserve its exact bytes, unknown
fields, GPS and metadata; do not normalize, redact or replace an existing original.
Check the [recording catalog](docs/development/RECORDINGS.md) and integrity tests.

Before submitting a new real recording, obtain explicit maintainer approval and
permission from its rights holder to publish the complete contents, including
GPS, timestamps and metadata. Agree its license and attribution first; the current
grant covers only the five listed recordings. Never attach a private recording to
a public issue or PR to ask whether publication is acceptable. Prefer minimal
synthetic reproductions when real data is unnecessary.

Contributed code uses GPL-3.0-or-later. Contributions to the licensed documentation
images and recording adaptations must respect their CC BY-SA 4.0 notices.
Do not introduce material you lack rights to contribute; identify third-party
code/assets and retain their notices. See [project licenses](README.md#license)
and [third-party boundaries](THIRD_PARTY_NOTICES.md).
