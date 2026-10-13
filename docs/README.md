# Documentation index

[Project README](../README.md) introduces the current scope and launch command;
[AGENTS.md](../AGENTS.md) defines repository workflow and agent instructions.
This directory contains project documentation, not generated artifacts or temporary files.

## Scope and design

- [Roadmap](ROADMAP.md): sequential milestones and exit criteria; M1 acceptance is verified.
- [Architecture](architecture/OVERVIEW.md): implemented foundation, planned subsystem
  boundaries and unverified scientific contracts.
- [ADR 0001](decisions/0001-platform.md): offline Windows platform and Python decision.
- [ADR 0002](decisions/0002-forces-source-contract.md): proposed M2 API, source ownership,
  device capabilities, resource limits and optional GPS policy.

## M2 importer specification (planned)

- [DEV-REQ-002](requirements/DEV-REQ-002-forces-importer.md): complete importer requirements and acceptance criteria.
- [Observed .forces variants](requirements/FORMAT-ANALYSIS.md): five-fixture schema comparison and unverified semantics.
- [M2 implementation plan](implementation/DEV-REQ-002/PLAN.md): staged scope, traceability and test gates.
- [Sequential Codex prompts](implementation/DEV-REQ-002/PROMPTS.md): one implementation task per invocation.

## Development

- [Windows setup and validation](development/SETUP.md): installation, all checks and
  VS Code Test Explorer configuration.
- [Python code quality](development/CODE_QUALITY.md): Pydantic, Ruff, Pylance,
  mypy, Pyright and regression-test scope.
- [Canonical models](development/CANONICAL_MODELS.md): immutable Stage 1 models,
  source ownership and diagnostic/result contracts.
- [Motion parsing](development/MOTION_PARSING.md): Stage 3 subset API, field policies
  and boundaries before complete importer integration.
- [Strict decoding](development/STRICT_DECODING.md): Stage 2 source API, resource
  budgets, schema dispatch and deterministic errors.
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
- [M2 Stage 0 inspection](validation/M2_STAGE0.md): recursive five-fixture evidence,
  integrity, validation and next-stage boundaries.
- [M2 Stage 1 models](validation/M2_STAGE1.md): synthetic acceptance evidence,
  requirement coverage and original stage boundaries.
- [M2 Stage 3 motion](validation/M2_STAGE3.md): five-recording validation, malformed
  input tests and incomplete full-import acceptance.
- [M2 Stage 2 decoding](validation/M2_STAGE2.md): strict decoder evidence and
  remaining complete-import/optional-data acceptance.
- [Node security follow-up](validation/DEPENDABOT.md): tested overrides, regression
  coverage and the open braces advisory.

Keep development instructions in `docs/development/`, architecture in
`docs/architecture/`, decision records in `docs/decisions/` and dated verification
results in `docs/validation/`. Temporary logs and downloads belong in `.tmp/`.
