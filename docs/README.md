# Documentation index

[Project README](../README.md) introduces the current scope and launch command;
[AGENTS.md](../AGENTS.md) defines repository workflow and agent instructions.
This directory contains project documentation, not generated artifacts or temporary files.

## Scope and design

- [Roadmap](ROADMAP.md): sequential milestones and exit criteria; M1 acceptance is verified.
- [Architecture](architecture/OVERVIEW.md): implemented foundation, planned subsystem
  boundaries and unverified scientific contracts.
- [ADR 0001](decisions/0001-platform.md): offline Windows platform and Python decision.

## M2 importer specification (planned)

- [DEV-REQ-002](requirements/DEV-REQ-002-forces-importer.md): complete importer requirements and acceptance criteria.
- [Observed .forces variants](requirements/FORMAT-ANALYSIS.md): four-fixture schema comparison and unverified semantics.
- [M2 implementation plan](implementation/DEV-REQ-002/PLAN.md): staged scope, traceability and test gates.
- [Sequential Codex prompts](implementation/DEV-REQ-002/PROMPTS.md): one implementation task per invocation.

## Development

- [Windows setup and validation](development/SETUP.md): installation, all checks and
  VS Code Test Explorer configuration.
- [Python code quality](development/CODE_QUALITY.md): Pydantic, Ruff, Pylance,
  mypy, Pyright and regression-test scope.
- [Real recordings](development/RECORDINGS.md): authorized fixture catalog and integrity checks.
- [Documentation tests](development/DOCUMENTATION_TESTS.md): markdownlint, CSpell
  and offline local-link checks.
- [Codex project settings](development/CODEX.md): project-local defaults, Context7
  and memory configuration.

## Verification evidence

- [M1 validation](validation/M1.md): current verified results, historical evidence
  boundaries and acceptance evidence.
- [M1 delivery plan](validation/M1_DELIVERY.md): branch, commit groups and PR verification order.
- [Dependency audit](validation/DEPENDENCIES.md): dated release checks and pinned tooling.
- [Node security follow-up](validation/DEPENDABOT.md): tested overrides, regression
  coverage and the open braces advisory.

Keep development instructions in `docs/development/`, architecture in
`docs/architecture/`, decision records in `docs/decisions/` and dated verification
results in `docs/validation/`. Temporary logs and downloads belong in `.tmp/`.
