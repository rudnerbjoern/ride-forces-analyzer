# Contributing

Keep contributions small and focused. Discuss substantial features in an issue
before implementation. Report vulnerabilities privately through [SECURITY.md](SECURITY.md).

## Set up and verify

Use native Windows, pinned versions and locked dependencies. Install matching
Node, then run PowerShell from the repository root:

```powershell
.\setup.ps1 -Development
.\start.ps1
```

- Video-export work: also run `.\setup.ps1 -VideoExport`.
- [Windows setup](docs/development/SETUP.md) owns versions, troubleshooting and
  required checks; do not install ad hoc environment packages.
- Start with focused behavior tests; add regressions for bug fixes.
- Before submission, run all applicable setup checks. Non-Windows results do not
  verify Windows/GUI behavior.
- Documentation-only changes: `npm run test:docs`.
- Delivery-skill tests: only when relevant implementation/inputs change.

## Pull requests

- Branch from current `main`; keep scope focused, without unrelated refactoring.
- Use the [PR template](.github/pull_request_template.md): problem, resulting
  behavior, actual check commands/results and remaining limits. Keep incomplete work
  in draft. CI must pass; maintainers review/merge.
- Follow the [commit format](.github/commit-message-instructions.md). Code,
  documentation and commits use English; user-facing changes maintain English/German
  UI text and layout fit.
- Follow [architecture constraints](docs/architecture/02_architecture_constraints.md):
  import, analysis, storage and rendering logic stay outside Qt widgets.
- Update existing behavior/limit documentation; no development diaries or weakened checks.
- Temporary artifacts: `.tmp/`. Never commit environments, exports, credentials or private logs.
- Coding agents also follow [AGENTS.md](AGENTS.md), including separate owner
  authorization for Git operations.

## Recordings and licenses

- Original `.forces` fixtures are read-only. Preserve bytes, unknown fields, GPS
  and metadata; never normalize, redact or replace originals.
  [Recording catalog](docs/development/RECORDINGS.md) and integrity tests define scope.
- New real recordings require explicit maintainer approval and rights-holder
  permission to publish complete contents, including GPS, timestamps and metadata. Agree license and
  attribution before submission; existing permission covers only the five listed originals.
- Never publish private recordings in issues/PRs to request approval.
  Prefer minimal synthetic reproductions when real data is unnecessary.
- Contributed code uses GPL-3.0-or-later; recording adaptations retain applicable
  CC BY-SA 4.0 duties. Documentation images follow the [central image guide](docs/images/README.md).
- Contribute only material you have rights to provide; identify third-party
  code/assets and retain notices. See [project licenses](README.md#license)
  and [third-party boundaries](THIRD_PARTY_NOTICES.md).
