# Backend API
Last updated: 2026-06-02

## Root
- `GET /`
  - Redirects to `/docs` when not in cloud mode.
  - Returns JSON health information in cloud mode.

## Workflows
- `GET /workflows`
- `POST /workflows`
- `GET /workflows/templates`
- `GET /workflows/{workflow_id}`
- `PUT /workflows/{workflow_id}`

## Executions
- `POST /executions/compile`
- `POST /executions`
- `GET /executions/{run_id}`
- `GET /executions/{run_id}/events`
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

## Boundary Rules
- HTTP and WebSocket handlers live under `app/server/api`.
- Request validation, response shape stability, and status code mapping are owned by the API layer.
- Long-running work is delegated out of request handlers to services and jobs rather than executed inline.
