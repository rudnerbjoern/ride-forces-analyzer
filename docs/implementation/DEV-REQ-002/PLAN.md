# M2 importer scope and acceptance

**Complete.** [Requirements](../../requirements/DEV-REQ-002-forces-importer.md)
define FR/NFR and AC-01–AC-10. [M2 acceptance](../../validation/M2.md) records
verification; this document scopes the implemented boundary.

| Boundary        | Implemented contract                                                                             | Requirement coverage               |
| --------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------- |
| Source / models | Owned immutable bytes/tree, numeric tokens, provenance and ordered diagnostics                   | FR-002–006, FR-023, FR-027         |
| Decoder         | Path/bytes, strict UTF-8/JSON, version 2.2.0 and resource budgets                                | FR-001, FR-003–010, FR-024, FR-026 |
| Motion          | Complete finite vectors, paired lengths, independent marker bounds and explicit absence/defaults | FR-011–016                         |
| Optional data   | Metadata/weather, ordered attributes and independently indexed GPS with retained defects         | FR-009–010, FR-017–022, FR-025     |
| Service         | Full results, repeatable/concurrent imports, offline read-only behavior                          | FR-028–030                         |

Absent rate/riding position use owner-approved 50/Seated defaults with provenance;
absent start/end independently use 0/N-1 with warnings. Source absence remains
unchanged. Supplied invalid core data fails; absent gravity/GPS is never invented.

Detailed behavior belongs in [ADR 0002](../../decisions/0002-forces-source-contract.md)
and the [public API guide](../../development/IMPORT_SERVICE.md).
The [format analysis](../../requirements/FORMAT-ANALYSIS.md) distinguishes observed
fixture data from unqualified semantics.

Acceptance covers all five authorized originals, exact byte/hash preservation,
unknown fields, deterministic diagnostics, malformed/bounded inputs, optional
recovery, Qt-free typed APIs and offline operation. Additional schemas require an
explicit contract; force interpretation, storage, UI and exports belong elsewhere.
