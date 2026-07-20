# Nodes And Execution
Last updated: 2026-07-20

## Nodes Page
- Filter the node catalog by category and search query.
- Review node input, output, and parameter summaries.
- Load predefined workflow templates into the workflow editor.
- Import custom manifest JSON.

## Execution Monitoring
Execution status is exposed through:

- Polling endpoint: `GET /executions/{run_id}`
- Event history endpoint: `GET /executions/{run_id}/events`
- WebSocket stream: `WS /executions/ws/runs/{run_id}`

Run statuses include `queued`, `running`, `completed`, `failed`, `cancelled`, and `paused`. Step states also include `skipped`; retry and timeout events are reported in the event history.

Runs are durable. The editor polls the persisted run state and can reconnect after a page reload or backend restart without re-executing durably completed steps. A paused human-review run exposes a resume token and can continue through the resume endpoint with an optional reviewed payload.

Cancellation is requested against the current durable run and may take effect after the active provider operation reaches a safe cancellation boundary.
