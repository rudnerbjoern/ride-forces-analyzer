# Documentation index

[Project README](../README.md) introduces the current scope and launch command;
[AGENTS.md](../AGENTS.md) defines repository workflow and agent instructions.
This directory contains project documentation, not generated artifacts or temporary files.

## Scope and design

- [Roadmap](ROADMAP.md): sequential milestones and exit criteria; M1 and M2 acceptance is verified.
- [Architecture](architecture/OVERVIEW.md): implemented foundation, planned subsystem
  boundaries and unverified scientific contracts.
- [ADR 0001](decisions/0001-platform.md): offline Windows platform and Python decision.
- [ADR 0002](decisions/0002-forces-source-contract.md): accepted M2 API, source ownership,
  device capabilities, resource limits and optional GPS policy.

## M2 importer specification (accepted)

- [DEV-REQ-002](requirements/DEV-REQ-002-forces-importer.md): complete importer requirements and acceptance criteria.
- [Observed .forces variants](requirements/FORMAT-ANALYSIS.md): five-fixture schema comparison and unverified semantics.
- [M2 implementation plan](implementation/DEV-REQ-002/PLAN.md): staged scope, traceability and test gates.
- [Sequential Codex prompts](implementation/DEV-REQ-002/PROMPTS.md): one implementation task per invocation.

## M3 scientific analysis specification (planned)

- [DEV-REQ-003](requirements/DEV-REQ-003-scientific-analysis.md): scientific
  calculations, required libraries, safeguards and acceptance criteria.
- [M3 implementation plan](implementation/DEV-REQ-003/PLAN.md): staged
  dependency, motion, filtering, GPS and validation tasks.
- [M3 Codex prompts](implementation/DEV-REQ-003/PROMPTS.md): one prompt per stage.

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
- [Optional parsing](development/OPTIONAL_PARSING.md): Stage 4 metadata, ordered
  attributes, independent GPS slots and nonfatal defect policies.
- [Import service](development/IMPORT_SERVICE.md): Stage 5 public Path/bytes API,
  full recordings, aggregate diagnostics, version policy and performance method.
- [Real recordings](development/RECORDINGS.md): authorized fixture catalog and integrity checks.
- [Documentation tests](development/DOCUMENTATION_TESTS.md): markdownlint, CSpell
  and offline local-link checks.
- [CI selection](development/CI.md): dependency check, conditional suites and required merge gate.
- [Dependabot policy](development/DEPENDABOT.md): scheduled uv/npm/Actions PRs and security-update settings.
- [Codex project settings](development/CODEX.md): project-local defaults, Context7
  and memory configuration.

## Verification evidence

- [M2 validation](validation/M2.md): final AC-01–AC-10 outcomes,
  native Windows checks, fixture integrity, traceability and successful PR CI.
- [M1 validation](validation/M1.md): current verified results, historical evidence
  boundaries and acceptance evidence.
- [M1 delivery plan](validation/M1_DELIVERY.md): branch, commit groups and PR verification order.
- [Dependency audit](validation/DEPENDENCIES.md): dated release checks and pinned tooling.
- [Node security follow-up](validation/DEPENDABOT.md): tested overrides, regression
  coverage and the open braces advisory.

Keep development instructions in `docs/development/`, architecture in
`docs/architecture/`, decision records in `docs/decisions/` and dated verification
results in `docs/validation/`. Temporary logs and downloads belong in `.tmp/`.
