# Nodes And Execution
Last updated: 2026-10-01

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

Runs are durable. The editor polls persisted state and retains the active run across page reloads. While paused, review the checkpoint, enter a JSON object in Reviewed payload, and select Resume Run or Cancel Run. A new workflow run remains disabled until the tracked run finishes or is cancelled.

If monitoring disconnects, close the error dialog and select Reconnect Run, or reload after the backend is available. Queued runs and runs interrupted between steps recover using completed outputs. A step interrupted while running fails closed with `RECOVERY_UNAVAILABLE`; inspect its possible side effects before starting another run. Durably completed steps are not re-executed.

Cancellation is requested against the current durable run and may take effect after the active provider operation reaches a safe cancellation boundary.
