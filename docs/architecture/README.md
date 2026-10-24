# Architecture — arc42

The twelve arc42 chapters below are the maintained architecture of Ride Forces
Analyzer. Update the relevant chapters when architecture changes; do not create
a parallel overview. Diagrams use Mermaid. Implemented behavior, planned work and
unverified scientific assumptions are explicitly distinguished.

## Contents

| Chapter | View                                                       | Contents                                                    |
| :------ | :--------------------------------------------------------- | :---------------------------------------------------------- |
| 01      | [Introduction and goals](01_introduction_and_goals.md)     | Scope, quality goals and stakeholders                       |
| 02      | [Architecture constraints](02_architecture_constraints.md) | Platform, offline processing and data protection            |
| 03      | [Context and scope](03_context_and_scope.md)               | External systems, users and interfaces                      |
| 04      | [Solution strategy](04_solution_strategy.md)               | Processing pipeline, boundaries and scientific policy       |
| 05      | [Building block view](05_building_block_view.md)           | Packages, responsibilities and public interfaces            |
| 06      | [Runtime view](06_runtime_view.md)                         | Qt startup, successful imports and failure paths            |
| 07      | [Deployment view](07_deployment_view.md)                   | Local Windows execution, development and release boundaries |
| 08      | [Cross-cutting concepts](08_concepts.md)                   | Source ownership, diagnostics, capabilities and validation  |
| 09      | [Architecture decisions](09_architecture_decisions.md)     | Accepted choices, rationale and deferred qualification      |
| 10      | [Quality requirements](10_quality_requirements.md)         | Testable quality scenarios and evidence                     |
| 11      | [Risks and technical debt](11_technical_risks.md)          | Scientific uncertainty and integration limits               |
| 12      | [Glossary](12_glossary.md)                                 | Domain and architecture vocabulary                          |

## Ownership

The [roadmap](../ROADMAP.md) owns milestone status and open work; API/product
guides define detailed current contracts. These chapters describe implemented
boundaries and explicit planned services. Chapter 09 records concise decision
status and rationale; scientific uncertainty remains explicit across these views.

This structure follows the [arc42 template sections](https://docs.arc42.org/home/)
and [arc42 method](https://arc42.org/method/). Keep documentation proportional to
implemented behavior; an empty future subsystem does not need invented internals.
