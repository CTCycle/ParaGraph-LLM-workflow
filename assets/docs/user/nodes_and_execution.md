# Nodes And Execution
Last updated: 2026-06-02

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

Common statuses include queued, running, completed, failed, and cancelled.
