# Findings And Remediation
Last updated: 2026-08-20

## Review Scope
The architecture review covered backend layering, SQLite lifecycle, manifest
persistence, execution durability, event sequencing, frontend contract drift,
and the size of `client/src/pages/WorkflowPage.tsx`.

## Implemented Remediations
- SQLite foreign keys are enabled centrally for application and migration
  connections. Regression tests cover the pragma and cascades.
- The obsolete application-database node-manifest mirror was removed through
  Alembic revision `0002_remove_node_configuration_mirror`. The filesystem
  manifest repository is now the single persistence boundary.
- Resume payload validation and reviewed-output construction remain in the
  execution service. The repository atomically consumes the checkpoint, token,
  step, and run transition.
- Durable event publication is serialized per process so concurrent publishers
  receive monotonic sequence numbers and history order.
- The mixed `server/domain` package was split into portable `server/contracts`,
  configuration settings, and service-owned runtime objects. An AST test
  prevents contracts from importing API, service, repository, or SQLAlchemy
  implementation layers.
- Workflow localStorage parsing and persistence moved from the route page to
  `client/src/workflow/hooks/workflowPersistence.ts` with focused unit tests.

## Validation Evidence
- Backend focused persistence, migration, manifest, execution, and event tests
  pass.
- Contract-boundary, frontend-contract, job, and provider route tests pass.
- Frontend type-check/build, lint, and the existing unit suite pass; the
  persistence module has an additional focused test.

## Follow-Up Work
- Continue decomposing `WorkflowPage.tsx` into execution control, graph I/O,
  interaction state, and presentation modules without changing editor behavior.
- Consolidate API response/error handling and generated/manual contract drift
  checks as endpoint payloads evolve.
- Revisit provider capability reporting, vector-store base contracts, and
  dependency-backed ML capability checks as separate bounded changes.
