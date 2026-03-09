# Refactor Audit

## Existing Frontend Structure
- The prior workflow page was a single ReactFlow component responsible for graph editing, persistence, validation, execution, and runtime output rendering.
- Node editing lived inside node cards, with runtime outputs written back into persisted node params.
- Graph persistence existed only as a legacy localStorage blob (`paragraph.workflow.graph`) without schema-version migration boundaries.

## Existing Backend Structure
- App runtime exposed only `/workflow` despite extra route modules in-tree.
- Workflow validation, compile-like checks, and execution lived in one executor module.
- Runtime updates relied on polling/job snapshots; no websocket event stream.
- Legacy template route modules (`upload/preparation/training/validation/inference`) were import-broken due missing entity modules and out of product scope.

## Critical Problems
1. Visual/editor state and runtime state were coupled.
2. There was no explicit compiled execution plan contract.
3. Runtime event payloads were not typed and were polling-only.
4. Node contracts were not formalized with execution semantics metadata.
5. Workflow persistence lacked versioning and dedicated repository/service seams.
6. Legacy non-workflow modules were stale and structurally misleading.

## Keep
- FastAPI app foundation, config loading, logging, and job manager.
- Existing `/workflow/*` compatibility surface for transition.
- Existing provider client implementations as adapter seed.
- Existing backend test suite as baseline regression safety.

## Keep With Adapter
- `/workflow/catalog`, `/workflow/validate`, `/workflow/execute`, `/workflow/jobs/{id}` are preserved via a legacy adapter over new workflow/compiler/execution services.
- Legacy localStorage graph is migrated once into schema-versioned workflow document state.
- Polling remains as fallback while websocket runtime events are primary.

## Rewrite
- Backend contract layer moved into dedicated workflow/execution/node-catalog entities.
- Compiler, execution orchestration, provider capability checks, and event publication extracted into dedicated services.
- Frontend graph/editor rebuilt around Canvas2D with non-reactive pointer state and separated stores.
- Workflow persistence moved to repository/service model with versioned artifacts.

## Delete
- Out-of-scope legacy server route modules:
  - `ParaGraph/server/routes/upload.py`
  - `ParaGraph/server/routes/preparation.py`
  - `ParaGraph/server/routes/training.py`
  - `ParaGraph/server/routes/validation.py`
  - `ParaGraph/server/routes/inference.py`

## Refactor Order
1. Audit artifact and stabilization.
2. Contract extraction and compatibility adapters.
3. Graph domain/store separation.
4. Canvas2D editor replacement.
5. Compiler + execution plan services.
6. Websocket runtime event stream.
7. Workflow/version persistence seams.
8. Provider capability normalization.

## Immediate Risks
- Existing tests currently cover legacy compatibility and core executor path; expanded coverage is still needed for websocket and workflow CRUD/version APIs.
- Canvas interaction complexity can regress quickly without dedicated frontend interaction tests.
- Provider capability matrix is foundational but not yet exhaustive for all advanced modes.

## Unknowns Requiring Inspection
- Long-term secret storage implementation (`SecretReference`) is still pending.
- Vector store backend prioritization (local vs pgvector vs Qdrant) remains product-priority dependent.
- RAG node runtime implementations are scaffold-level and need full MVP behavior hardening.