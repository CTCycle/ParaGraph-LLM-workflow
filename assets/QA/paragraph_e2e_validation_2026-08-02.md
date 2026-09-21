# ParaGraph End-to-End UI and System Validation

Date: 2026-08-02

## 1. Executive summary

The live application passed the requested UI, API, error-state, responsive, accessibility-basics, and persistence checks. The frontend and backend remained synchronized for invalid compilation, provider connectivity failure, durable execution failure, and configuration refresh. No blocking UI or integration defect was confirmed.

One quality-gate issue was reproduced: the configuration profile modal unit test exceeded Vitest's default 5-second test budget under the full suite, although the flow completed in isolation. The test now has an explicit 15-second budget; the full suite passes 31/31 tests.

Provider-backed success was not claimed because the persisted Ollama endpoint is `http://127.0.0.1:1` and no Ollama service is running. The test deliberately used that local-only provider path instead of sending prompts through the persisted external OpenAI credential.

## 2. Tested areas

### Pages and flows

- Workflow landing page: initial render, status, canvas, toolbar, no console errors.
- Nodes: navigation, catalog load, category/search filtering, add-node intent to workflow, invalid run diagnostics.
- Nodes templates: chat template load, provider/model selection, valid compile, execution start, polling, failure modal.
- Models: Ollama public catalog load, Hugging Face catalog load, search, pull-state filtering.
- Configurations: persisted configuration load, invalid Ollama connectivity check, error alert semantics, refresh persistence.
- Responsive workflow and configuration checks at 1280x720 and 390x844.
- Keyboard focus-visible check on primary navigation.

### Backend endpoints observed

- `GET /docs`, `GET /openapi.json`
- `GET /nodes/catalog`
- `GET /workflows/templates`
- `GET /providers/models?session_name=default`
- `GET /providers/ollama/library?session_name=default`
- `GET /providers/huggingface/models?...`
- `GET /configurations?session_name=default`
- `POST /configurations/ollama/ping`
- `POST /executions/compile`
- `POST /executions` (`202 Accepted`)
- Repeated `GET /executions/df90c79a`
- `GET /executions/df90c79a/events`

## 3. Findings

### F-001: Configuration profile modal test exceeded default suite timeout

- Severity: low
- Area: QA/test reliability
- Steps: run `npm.cmd run test:unit` from `app/client` before the fix.
- Expected: all profile modal tests complete within the configured Vitest budget.
- Actual: 30 tests passed and the profile modal flow timed out at 5,278 ms.
- Evidence: the same test passed in isolation in 1.9 seconds with a 15-second budget. The test now uses an explicit 15-second timeout, and the full suite passes 8/8 files and 31/31 tests.
- Fix: `src/pages/ConfigurationsPage.test.tsx` received the scoped timeout adjustment; no product behavior was changed.

## 4. UI and UX observations

- The dark visual system, spacing, focus rings, active navigation underline, node cards, and status treatments were consistent across the inspected desktop surfaces.
- Invalid workflow compilation produced both an inline diagnostics region and a modal with actionable checks. The Run button became disabled after the blocking compile response.
- The provider failure modal named the failed `llm_chat_1` step and preserved the graph, rather than showing false success.
- At 390x844, the top navigation remains keyboard-visible and usable through its responsive wrapping/scroll treatment; the configuration panels stack within the viewport without document overflow.
- The workflow canvas remains pannable/zoomable at mobile width; graph nodes can extend beyond the initial viewport as expected for a canvas surface.
- Focus-visible inspection showed a blue outline and shadow ring on the primary navigation link.

## 5. Backend and integration observations

- The invalid Text Output graph produced `POST /executions/compile` with HTTP 200 and surfaced compiler diagnostics in the UI; this matches the API's diagnostic-response contract rather than a transport failure.
- The valid template produced `POST /executions` with HTTP 202, a durable run ID `df90c79a`, polling requests, and event history.
- Direct run inspection returned `status: failed`; completed prompt/model-provider steps, failed `llm_chat_1`, and queued `text_output_1`. The UI showed the same error text as the API and events.
- The local Ollama status check returned an inline error and logged `POST /configurations/ollama/ping` with HTTP 200. The backend log correlated the refused local connection to `127.0.0.1:1`.
- Ollama public catalog and Hugging Face public catalog calls completed successfully. Their data is external and time-sensitive.
- Browser console logs were empty after the full interaction pass. No blocking asset or document-overflow issue was observed.

## 6. Unverified concerns

- Successful provider-backed execution was not verified because no local Ollama listener is available. External OpenAI execution was intentionally not attempted.
- Real-time WebSocket execution streaming was not exercised because the local-only run failed before a successful streaming scenario.
- File upload/import and database schema flows were not exercised in this pass; they require additional fixtures or a deliberate file/database side effect.

## 7. Recommended next actions

1. Keep the explicit profile-flow test timeout and monitor suite duration in CI.
2. For a provider-success QA pass, start an authorized local Ollama service and rerun the template through completion, including reload during an active durable run.
3. Add a dedicated browser/API contract case for WebSocket event streaming and a fixture-backed custom-node import flow.

## Evidence artifacts

- `paragraph-e2e-initial.png`
- `paragraph-e2e-invalid-workflow.png`
- `paragraph-e2e-config-error.png`
- `paragraph-e2e-mobile-workflow.png`
- `paragraph-e2e-mobile-config.png`
- `paragraph-e2e-final.png`

