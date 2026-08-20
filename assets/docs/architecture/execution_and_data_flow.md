# Execution And Data Flow
Last updated: 2026-08-20

## Layered Backend Flow
Typical backend flow follows endpoint to service to repository:

- Workflows:
  - `api/workflows.py` -> `services/workflow/workflow.py` -> `repositories/workflow/workflow.py`
- Execution lifecycle:
  - `api/executions.py` -> `services/workflow/compiler/service.py` and `services/workflow/execution.py` -> SQLAlchemy-backed run, step, and event repositories
- Configurations:
  - `api/configurations.py` -> `services/configuration.py` -> `repositories/configuration.py` -> SQLAlchemy models in `repositories/schemas/models.py`
- Provider catalogs and downloads:
  - `api/providers.py` -> `services/workflow/provider/service.py` plus helper, catalog, download, cache, and job modules under `services/workflow/provider/`
- Node catalog and imported manifests:
  - `api/nodes.py` -> `services/workflow/nodes/registry.py` -> `repositories/workflow/node_manifest.py`
- Database node operations:
  - `services/workflow/node_handlers/database/operations.py` -> `repositories/workflow/database.py`

## Responsibilities Of Key Modules
- `server/api/*`
  - HTTP and WebSocket boundary, request validation, and HTTP status mapping.
- `server/contracts/*`
  - Portable request and response models, workflow schema, node catalog
    contracts, and execution payloads. This layer does not depend on API,
    service, repository, or SQLAlchemy implementation modules.
- `server/configurations/settings.py`
  - Environment-backed settings and runtime configuration models.
- `server/services/workflow/compiler/service.py`
  - Graph validation, diagnostics, and topological planning.
- `server/services/workflow/execution.py`
  - Step orchestration, cache behavior, output shaping, pause/resume payload
    validation, and event publishing.
- `server/services/workflow/structured_models.py`
  - Structured JSON model inference, schema generation, Pydantic-source parsing, and validation payload formatting.
- `server/services/workflow/provider/service.py`
  - Provider facade, model metadata, OpenAI-compatible local provider discovery, and download orchestration.
- `server/services/workflow/provider/helpers.py`
  - Shared provider constants, metadata, and coercion helpers.
- `server/services/workflow/provider/ollama.py`
  - Ollama library adapter and cache and fetch mixin behavior.
- `server/services/workflow/provider/huggingface_catalog.py`
  - Hugging Face catalog adapter, caching, and local metadata behavior.
- `server/services/workflow/provider/huggingface_downloads.py`
  - Download lifecycle, manifests, progress, cleanup, and integrity validation.
- `server/services/workflow/node_handlers/core/prompts.py`
  - Prompt, prompt-template, and image-input executors used by the core handler registry.
- `server/services/llm/providers.py`
  - Runtime clients for Ollama, cloud providers, and OpenAI-compatible local providers such as LM Studio and llama.cpp.
- `server/services/workflow/node_handlers/processing/sources.py`
  - Fragment source hydration and measurement helpers.
- `server/services/workflow/node_handlers/processing/merge.py`
  - Merge-small-chunks executor.
- `server/services/workflow/node_handlers/structured.py`
  - Structured input and output, JSON validation, and output parsing executors.
- `server/services/workflow/node_handlers/http.py`
  - SSRF-guarded HTTP method node executors.
- `server/services/workflow/node_handlers/rag.py`
  - HTML cleanup, OCR availability reporting, context building, citations, and grounding checks.
- `server/services/workflow/node_handlers/advanced_text.py`
  - Deterministic text extraction, classification, redaction, parsing, and normalization.
- `server/services/workflow/node_handlers/control.py`
  - Branching, batching, caching, human review gates, and trace or debug helpers.
- `server/services/workflow/nodes/registry.py`
  - Node manifest validation, runtime handler lookup, plugin loading, parameter validation, and execution.
- `server/services/jobs.py`
  - Thread-based background job management.
- `server/services/runtime/events.py`
  - Durable per-run event history plus process-local live subscriber queues.
- `server/repositories/workflow/workflow.py`
  - Filesystem workflow storage and indexing.
- `server/repositories/workflow/node_manifest.py`
  - Filesystem node manifest loading, import persistence, test storage overrides, and rollback deletion.
- `server/repositories/workflow/database.py`
  - Bounded engine reuse, credential-safe connection identity, schema inspection, read-only enforcement, parameterized SQL, and transactional CRUD/bulk/upsert persistence.
- `server/repositories/workflow/execution_run.py`
  - Atomic run/step/event state changes, including one-time pause-checkpoint
    consumption. Reviewed payload validation and output shaping stay in the
    execution service.
- `server/repositories/configuration.py`
  - Session, profile, and access-key persistence in the application database.
- `server/repositories/database/sqlite.py`
  - Embedded SQLite engine, application schema access, and dataframe/tabular persistence behavior.
- `client/src/pages/WorkflowPage.tsx`
  - Visual workflow editor and execution control surface. Workflow localStorage
    parsing and persistence are isolated in
    `client/src/workflow/hooks/workflowPersistence.ts` while the remaining
    page decomposition proceeds incrementally.
- `client/src/workflow/components/*`
  - Workflow-local presentation components reused by the editor.
- `client/src/workflow/schema/*`
  - Workflow API and domain types plus editor-facing contracts.
- `client/src/app/services/*.ts`
  - Typed frontend API clients.

## Async And Background Behavior
- Most REST handlers are synchronous `def` handlers for CRUD, listing, and compile operations.
- Explicit async handlers are limited to:
  - `POST /nodes/uploads/directory` for multipart uploads.
  - `WS /executions/ws/runs/{run_id}` for streaming run events.
- Long-running workflow execution is offloaded to background threads through `JobManager`.
- Runs persist their compiled plan and completed step outputs. Startup recovery resumes queued or interrupted runs after completed steps; it never re-executes a durably completed step.
- Per-step timeouts prevent late results from updating durable state, but Python cannot forcibly terminate an underlying provider thread. Live WebSocket subscribers remain process-local and clients reconnect to durable history after restart.
- Async handlers avoid CPU-heavy loops; blocking workflow execution happens in job threads instead of request handlers.

## Compiler Diagnostics
- Compiler errors block plan creation; warnings are returned with an otherwise valid plan.
- Active nodes in independent graph components are compilation errors. A detached side-effecting node is also an error; a pure singleton workflow remains valid.
- Graph warnings cover missing terminal outputs, pure disconnected nodes, nodes that do not contribute to terminal outputs, and connections from conditional branch outputs.
- Workflow node instances accept optional `timeout_ms` and `retries` values, which are copied into execution steps.
- Non-positive timeouts, negative retry counts, and retries on side-effecting nodes without an idempotency contract block compilation.
- Conditional branch warnings describe the current missing-value activation model. Explicit activation tokens and catch or iteration regions require separate execution-engine support.
- Human-review pauses persist a run-scoped checkpoint and resume token; a successful resume consumes the token and injects the reviewed object into the gate's `result` output.
- Durable event sequence allocation is serialized at the publish boundary so
  concurrent publishers cannot create duplicate or out-of-order sequence
  history for one run.
- Tool collections expose serializable metadata plus an opaque runtime collection identity. Executable callables are scoped to the current run, async callables are awaited, and provider tool selection currently reports `prompt_emulated` until a native protocol adapter exists.
