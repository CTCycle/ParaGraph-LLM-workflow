# Backend API
Last updated: 2026-10-21

## Root
- `GET /`
  - Redirects to `/docs` when not in cloud mode.
  - Returns JSON health information in cloud mode.

## Workflow Templates
- `GET /workflow-templates`
  - Returns validated, read-only workflow template manifests from the configured
    resource root.

The browser owns the active workflow graph. The frontend sends that graph to
`POST /executions/compile`; the backend does not expose workflow CRUD or a
server-side workflow graph index.

## Executions
- `POST /executions/compile`
- `POST /executions`
- `GET /executions/{run_id}`
- `GET /executions/{run_id}/events`
- `POST /executions/{run_id}/cancel`
- `POST /executions/{run_id}/resume`
- `WS /executions/ws/runs/{run_id}`

## Nodes
- `GET /nodes/catalog`
- `POST /nodes/import`
- `POST /nodes/uploads/directory`
  - Multipart upload endpoint.
- `POST /nodes/check-database-connection`
- `POST /nodes/database-schema`
- `POST /nodes/check-vector-store-connection`

## Providers
- `GET /providers/catalog`
- `GET /providers/models`
- `GET /providers/ollama/library`
- `POST /providers/ollama/pull`
- `GET /providers/huggingface/models`
- `POST /providers/huggingface/download`
- `GET /providers/huggingface/download/{job_id}`
- `DELETE /providers/huggingface/download/{job_id}`

## Configurations
- `GET /configurations`
- `PUT /configurations`
- `GET /configurations/profiles`
- `GET /configurations/profiles/{profile_name}`
- `PUT /configurations/profiles/{profile_name}`
- `POST /configurations/ollama/ping`
- `POST /configurations/providers/ping`

Configuration payloads use `provider_configurations`. Public reads redact API
keys and expose `has_api_key`; the provider catalog is the authoritative list
of supported providers and defaults.

## Internal Database
- `GET /database/configuration` returns the selected SQLite path, active status,
  and any recovery error.
- `POST /database/test` checks a draft path without activating it. Invalid or
  unavailable targets return `400`.
- `PUT /database/configuration` prepares the target schema and its own settings,
  then atomically persists and activates it. An active workflow returns `409`;
  target preparation failures return `503` and keep the current database active.
  Switching never copies application data.

## Chat History
- `GET /chat-history`
  - Reads one history scope using `workflow_id`, `execution_session_id`,
    `node_id`, and `node_type` query parameters.
- `POST /chat-history/reset`
  - Clears only the selected Chat history scope. The request body is a
    `ChatHistoryHandle`.

Chat history scopes are keyed by workflow, execution session, and Chat node.
The `execution_owned` flag is carried by runtime handles so the execution
service can distinguish Chat history from standalone memory-node history; it
does not change the reset endpoint's scope selection.

`CHAT_HISTORY_MEMORY` is process-local. `CHAT_HISTORY_PERSISTED` uses the
application SQLite database. There is no filesystem chat-history API.

## Boundary Rules
- HTTP and WebSocket handlers live under app/server/api.
- Request validation, response shape stability, and status-code mapping are owned by the API layer.
- Long-running work is delegated to services and jobs rather than executed inline in request handlers.
- app/client/src/workflow/schema/apiTypes.generated.ts is generated from FastAPI OpenAPI component schemas; app/tests/unit/server/test_server_boundaries.py checks it for drift.
- Provider configuration and catalog metadata share the provider registry, which defines supported providers and defaults.
