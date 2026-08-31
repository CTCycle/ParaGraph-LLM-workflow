# Findings And Remediation
Last updated: 2026-08-31

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
- Backend workflow CRUD and filesystem workflow indexing were removed. The
  browser is the active-graph owner; read-only templates remain under the
  resource root and execution accepts validated graph payloads.
- Provider configuration records and the provider/model catalog now share one
  registry-backed contract. Legacy access-key and nested Ollama persistence
  paths were removed.
- Runtime configuration rejects obsolete JSON and invalid numeric environment
  values, frontend/backend ports are explicit, and unversioned application
  databases fail closed instead of being adopted heuristically.
- Frontend API DTOs are generated from the FastAPI OpenAPI schema and checked
  for freshness in the backend test suite.
- Persisted pause checkpoints reject unknown fields and malformed or
  status-inconsistent payloads instead of returning legacy state.
- Vector adapter capabilities now have one typed contract consumed by the
  catalog, editor, compiler, and runtime. Unsupported retrieval options fail
  closed, and score semantics and recursive overlap behavior are explicit.
- Database operation contracts retain credential profiles and opaque credential
  references, bind SQL parameters, enforce read-only execution, and reject
  unsupported MySQL upserts explicitly.
- Controller dependencies are now explicit typed graph edges. Global-node UI
  state and compiler injection were removed, and structured JSON editors mark
  same-name upstream bindings while retaining literals as fallbacks.

## Validation Evidence
- Backend focused persistence, migration, manifest, execution, and event tests
  pass.
- Contract-boundary, frontend-contract, job, and provider route tests pass.
- Frontend type-check/build, lint, and the existing unit suite pass; the
  persistence module has an additional focused test.
- The browser mock backend uses the canonical provider configuration and
  provider-catalog responses.

## Follow-Up Work
- Continue decomposing `WorkflowPage.tsx` into execution control, graph I/O,
  interaction state, and presentation modules without changing editor behavior.
- Consolidate API response/error handling and generated/manual contract drift
  checks as endpoint payloads evolve.
- Validate external vector, database, and model providers when services are
  available; local validation does not substitute for those provider checks.
