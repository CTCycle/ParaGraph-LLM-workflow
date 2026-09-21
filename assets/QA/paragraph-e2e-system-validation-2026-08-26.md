# End-to-End UI & System Validation

Date: 2026-08-26  
Repository: `ParaGraph LLM Workflow` on `develop`  
Frontend: `http://127.0.0.1:8002` / `http://localhost:8002`  
Backend: `http://127.0.0.1:5002`  
Browser: Chrome control with the live application

## 1. Executive Summary

The application passed the core full-stack validation. The landing page, navigation, node library, configuration page, model catalogs, workflow editor, backend compilation, WebSocket execution updates, and persisted workflow graph all behaved coherently in the live browser. The browser console remained free of errors and warnings during the final checked flows.

One low-severity UI defect was found and fixed during the pass: the node preview summary displayed `1 nodes match the current filters.` for a single result. It now uses grammatically correct singular/plural wording, with a regression assertion.

Provider-dependent success paths could not be proven in this environment. The saved Ollama endpoint is intentionally unreachable at `http://127.0.0.1:1`, and the configured OpenAI account returned HTTP 429 for insufficient quota. Both failures were surfaced by the UI and correlated with backend evidence; neither produced a false success.

## 2. Tested Areas

| Area | Result | Live/backend evidence |
| --- | --- | --- |
| Landing and navigation | Pass | `/` loaded with stable top bar, canvas, and navigation links; `/nodes`, `/models`, and `/config` navigated correctly. |
| Node library and filters | Pass after fix | `GET /nodes/catalog` returned 73 nodes, including `PROMPT` and `TEXT_OUTPUT`; category, search, and empty-result states updated correctly. |
| Custom node validation | Pass | Invalid JSON stayed in the modal with a clear client-side message; duplicate `PROMPT v1` returned HTTP 422 with the same detail rendered by the UI. |
| Configuration form | Pass | `GET /configurations?session_name=default` returned configuration data; Ollama ping returned HTTP 200 with `ok: false`, and the UI displayed the connection failure. |
| Models Explorer | Pass with expected provider failure | Live Ollama library and Hugging Face catalog data rendered; search and filters worked. Pulling `tinyllama` correctly surfaced local Ollama refusal with a retry state. |
| Deterministic workflow execution | Pass | A Prompt → Text Output graph compiled and completed through the UI; backend run `94e70dbe` was `completed` with two completed steps and the expected output. |
| OpenAI-backed workflow execution | Expected environment failure | The chat template started through the UI, backend logged `POST https://api.openai.com/v1/chat/completions` HTTP 429, and the UI showed a detailed execution-error modal. |
| Refresh/navigation persistence | Pass for graph state | Two nodes, one edge, and the edited prompt survived refresh and back/forward navigation. Runtime output resets on refresh; see unverified concerns. |
| Responsive behavior | Pass | Wide desktop and 1024px supported layouts retained the application; a 900px viewport showed the desktop-width gate. |
| Console/accessibility basics | Pass | No live console errors/warnings; visible controls had accessible names, form inputs were label-wrapped, Escape dismissed the import dialog, and Tab advanced from the Ollama search field to its state filter. |

## 3. Findings

### F-001 — Singular node-count summary used plural grammar

Severity: Low — fixed  
Area: UI

Steps to reproduce before the fix:

1. Open Nodes.
2. Search for `secure http` or select a filter that leaves one node.
3. Read the Node preview summary.

Expected: `1 node matches the current filters.`  
Actual before fix: `1 nodes match the current filters.`

The issue was corrected in `app/client/src/pages/NodesPage.tsx` with a small formatter that handles both noun and verb agreement. A regression assertion was added to `app/client/src/pages/NodesPage.test.tsx`.

Live recheck after rebuilding the frontend showed `1 node matches the current filters.` and the zero-result state showed `0 nodes match the current filters.`

### F-002 — Default Vite build cleanup is blocked by a managed cache placeholder

Severity: Low — environment/tooling  
Area: Build verification

`npm run build` completed TypeScript compilation, then Vite failed while trying to unlink the pre-existing ignored file `app/tests/cache/frontend-dist/.gitkeep` with `EPERM`. The file and directory are ACL-managed in this checkout and could not be renamed or removed.

The source build itself was verified with:

- `npm exec -- vite build --outDir=".../assets/QA/frontend-dist-qa" --emptyOutDir` — passed.
- `npm exec -- vite build --emptyOutDir=false` — passed.
- The live preview was served from the rebuilt QA output and the browser recheck passed.

No application source change was made for this environment-specific cache permission issue.

## 4. UI and UX Observations

- The dark visual system is consistent across the top navigation, page headers, cards, controls, and status banners.
- The workflow canvas provides a clear node/edge model, visible React Flow controls, node editing, fit-to-view, and an explicit node-tree toggle.
- The filtered node screenshot shows a readable single-card empty-space state after narrowing the catalog.
- Models and Configurations use dense two-column layouts at desktop sizes. The model catalogs correctly use independent scroll regions rather than expanding the page indefinitely.
- Error feedback is visually prominent and semantically marked: configuration failures use an alert-style banner, while workflow execution failures use a modal with a close control and detailed context.
- Focus rings were visible on keyboard-focused controls. The basic DOM audit found no unnamed interactive controls on the node page; configuration inputs were wrapped by labels.
- The visual review was evidence-based at the default Chrome viewport and explicit desktop sizes. It was not a formal WCAG contrast certification.

Screenshots:

- [Node library after the copy fix](paragraph-nodes-e2e-fixed.png)
- [Configuration Ollama failure state](paragraph-config-ollama-error.png)
- [Live models catalog](paragraph-models-catalog.png)
- [Successful deterministic workflow](paragraph-workflow-e2e-final.png)

## 5. Backend and Integration Observations

The backend contract inventory returned HTTP 200 for `/openapi.json` with 29 routes, including `/executions/compile`, `/nodes/import`, and `/configurations/ollama/ping`.

Observed API checks:

- `GET /nodes/catalog` — HTTP 200; 73 nodes; one Prompt and one Text Output manifest.
- `GET /workflows/templates` — HTTP 200; 3 templates.
- `GET /configurations?session_name=default` — HTTP 200; response shape contained `session_name`, `access_keys`, and `ollama`. Secret values were not read into the report.
- `POST /nodes/import` with the existing Prompt manifest — HTTP 422; `Node manifest already exists for PROMPT v1`. The browser showed the same backend detail.
- `POST /configurations/ollama/ping` with the configured non-running endpoint — HTTP 200; `ok: false`; local connection-refusal message. The UI converted it to `Error: Ollama unreachable. Check that Ollama is running at http://127.0.0.1:1.`
- Deterministic UI execution — backend logged request `aec158e195774c84b20849ca98ed4374`, job `94e70dbe`, and WebSocket acceptance/open/close. `GET /executions/94e70dbe` returned `status: completed`, two completed steps, the `text_output_mta6hha2_1o5z` output, and no error.
- OpenAI-backed template execution — backend logged job `a06eea7c` followed by `POST https://api.openai.com/v1/chat/completions` HTTP 429; the UI showed the provider error rather than claiming completion.
- Models catalog loads — backend logged HTTP 200 responses from `https://ollama.com/library` and Hugging Face model/tag APIs.

The selected Chrome control surface exposed console and DOM state but not a network-waterfall export. Network correlation therefore used the backend request logs together with direct API checks; no proxy/CORS failure was observed.

## 6. Unverified Concerns

- A successful Ollama execution/model pull remains unverified because no Ollama server was listening at the configured endpoint. A successful OpenAI execution remains unverified because the configured account has no remaining credits.
- After refresh, the graph and edited parameters persisted, while the runtime Text Output returned to its default display. This is likely intentional transient-runtime behavior, but product requirements should explicitly state whether the last execution output is expected to persist.
- At the explicit 1024px viewport, Chrome reported a fractional layout width of approximately 1024.51px and rounded body client/scroll widths to 1025px. No visible clipping or horizontal scrollbar was observed; this appears consistent with browser/device-pixel rounding and should be monitored rather than treated as a confirmed defect.
- Unit tests emit existing React Router future-flag warnings in `DatabaseSchemaPage.test.tsx`; no corresponding live-browser warning was observed.

## 7. Verification Gates

- Frontend lint: passed.
- Frontend unit suite: passed — 9 test files, 32 tests.
- Frontend TypeScript compilation: passed as the first phase of `npm run build`.
- Frontend Vite bundle: passed with the cache-preserving/QA output commands described in F-002.
- Backend Ruff: passed — `python -m ruff check server tests`.
- Backend test suite: passed — 332 tests, 1 existing dependency deprecation warning.
- Live Chrome console: no errors or warnings in the final checked tabs.

## 8. Recommended Next Actions

1. No further code action is required for F-001; the fix and regression assertion are complete.
2. Provide a reachable Ollama test instance and a funded/isolated OpenAI test credential when provider-success coverage is required.
3. Decide whether runtime outputs should persist across refresh, then document or implement that behavior explicitly.
4. Repair the managed ACL or cache policy for `app/tests/cache/frontend-dist/.gitkeep` so the normal `npm run build` command can empty its configured output directory.
5. Optionally opt the React Router test harness into the existing future flags to remove the unit-test warnings.

## Cleanup

The backend and frontend preview processes started for this validation were task-scoped and should be stopped after report generation. Generated screenshots and this report remain under `assets/QA/`; the temporary QA frontend distribution should be removed during final process cleanup.
