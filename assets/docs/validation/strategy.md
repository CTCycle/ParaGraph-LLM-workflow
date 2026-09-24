# Validation Strategy
Last updated: 2026-09-24

## Purpose and authority

This document is the durable campaign map for validating ParaGraph from its
clean baseline through provider-backed and resilience workflows. It is a
digest of the comprehensive validation roadmap, not a replacement for the
evidence reports.

- [`project_status_ledger.md`](../project_status_ledger.md) is the canonical
  current-status summary.
- [`assets/QA`](../../QA/README.md) contains the curated, revision-scoped
  reports and visual evidence.
- Source inspection, the existence of a test, a catalog mapping, or a mocked
  response is not a product `PASS` by itself.
- Claims are scoped to the exact revision, environment, provider/service, and
  workflow path recorded by the evidence. A deterministic local run does not
  validate a model provider, and a backend test does not validate browser UX.

## Campaign tiers

Validation proceeds from cheap, deterministic foundations toward stateful and
external integrations. The slice IDs are stable so later reports can be
compared without rewriting the status ledger.

| Tier | Focus | Slice IDs | Exit signal |
| --- | --- | --- | --- |
| 0 | Clean CI, Windows bootstrap, launcher lifecycle, and evidence integrity | `PG-T0-01`–`PG-T0-04` | A reproducible baseline exists and no Tier 0 slice is an unresolved `FAIL`. |
| 1 | Routes, API boundary, configuration/secrets, browser-local workflow persistence, and SQLite application persistence | `PG-T1-01`–`PG-T1-05` | Foundation flows are exercised against the current candidate revision. |
| 2 | Node catalog/templates, custom import, graph editing, compiler diagnostics, deterministic execution, lifecycle controls, and restart/event replay | `PG-T2-01`–`PG-T2-08` | Core product workflows have browser and durable-state evidence. |
| 3 | Deterministic node families, documents/chunks, structured data, retrieval, uploads, local database/vector adapters, HTTP nodes, and tools | `PG-T3-01`–`PG-T3-11` | Each supported local capability family has representative runtime evidence. |
| 4 | Ollama/Hugging Face management and runtime, cloud/local provider execution, and Chat history | `PG-T4-01`–`PG-T4-05` | Provider-specific success and controlled-failure paths are reported separately. |
| 5 | Malformed input, transport/security limits, destructive launcher actions, accessibility/guidance, and performance | `PG-T5-01`–`PG-T5-05` | Resilience and safety claims have direct evidence with no unresolved critical regression. |

The recommended order is Tier 0, Tier 1, Tier 2, deterministic/local Tier 3,
provider/external Tier 4, and Tier 5 resilience. Provider availability must
not delay clean CI or deterministic foundations, and blocked external services
must remain explicitly `BLOCKED` rather than being converted into a mocked
success claim.

## Tier 1 slices

| Slice | Scope | Exit signal |
| --- | --- | --- |
| `PG-T1-01` | Provider and configuration HTTP route behavior, including representative success and error-to-status mappings. | Focused route checks pass; stubbed provider responses are not reported as provider success. |
| `PG-T1-02` | FastAPI OpenAPI surface and generated frontend API contract alignment. | The generated contract check matches the current OpenAPI schemas. |
| `PG-T1-03` | Configuration and named-profile reads/writes, secret redaction, and preservation of saved keys on redacted updates. | Disposable SQLite integration checks and the focused configuration UI suite pass. |
| `PG-T1-04` | Browser-local workflow graph save, reload, and navigation persistence. | Browser evidence confirms the graph survives reload and back/forward navigation. |
| `PG-T1-05` | SQLite persistence for execution runs, steps, outputs, checkpoints, and events. | Repository and restart/recovery evidence confirms durable records on the current candidate. |

## Tier 0 slices

Tier 0 was the campaign's initial validation tier. The current ledger records
Tier 0 and Tier 1 as complete; the next actionable work is the Tier 2 browser
workflow campaign, beginning with the catalog/template and custom-import gaps.
The intended Tier 0 boundaries remain:

### `PG-T0-01` — clean CI baseline

Run backend lint/compile/tests and frontend install/lint/build/unit tests on a
clean checkout of the exact revision. The Vite build requires
`FASTAPI_HOST`, `FASTAPI_PORT`, `UI_HOST`, `UI_PORT`, and
`VITE_API_BASE_URL`; CI must provide these safe local values rather than rely
on a developer-only `settings/.env`. Browser E2E and provider services are out
of scope. The adjacent regression is the full configured CI job set.

The intake failure at `6a9e5e142898d5a1ab6f8c4d80693d5b5ff5ba40` is recorded in
[`PG-T0-01-6a9e5e1.md`](../../QA/PG-T0-01-6a9e5e1.md): backend and frontend
lint passed, while the clean frontend build stopped at the first missing
environment value and frontend unit tests were skipped.

### `PG-T0-02` — fresh Windows bootstrap and migrations

From a disposable data root, exercise launcher option 3 and option 5 with a
missing environment file, first and repeated dependency setup, an empty
SQLite database, repeat migration, and an intentionally incompatible schema.
The expected result is idempotent setup and fail-closed preservation of an
incompatible database. Never remove real user data for this slice.

### `PG-T0-03` — launcher start and shutdown

From no ParaGraph processes, exercise launcher options 1 and 2. Capture
backend health before frontend launch, the documented visible backend
terminal, configured port ownership, UI/docs reachability, process-tree
cleanup, and immediate relaunch. A port collision is a controlled scenario,
not permission to kill unrelated processes.

### `PG-T0-04` — evidence integrity

Every ledger link must resolve to a tracked report or explicitly state that the
source artifact is unavailable. Reports must carry slice ID, revision,
planned/executed scenarios, status, failure class, root cause/fix when known,
regression result, evidence paths, gaps, prerequisites, date, and environment.
Generated caches, test databases, credentials, and bulk temporary outputs stay
out of the curated remote evidence set.

## Evidence and status rules

Each slice report should be named `PG-Tx-yy-<tested-revision>.md` (or use a
directory with the same stable prefix) and include:

1. scope and explicit out-of-scope behavior;
2. exact planned and executed scenarios;
3. status: `PASS`, `PARTIAL`, `FAIL`, `BLOCKED`, or `UNTESTED`;
4. failure class: `FUNC`, `FE`, `BE`, `INT`, `STATE`, `PERF`, `UX`, `CFG`, or
   `ENV`;
5. tested revision, OS/runtime/browser/service versions, and date;
6. root cause, surgical fix, and adjacent regression results where applicable;
7. links to logs, screenshots, traces, run IDs, or database state; and
8. remaining gaps and external prerequisites.

Use the sequence **inspect → execute → observe → diagnose → fix → retest →
adjacent regression → record**. After each fix, run the affected scenario and
its smallest adjacent regression. Once a tier is stable, run its relevant
automated tests plus one representative E2E path. Reserve full campaign
regression for the candidate revision near completion.

## Completion boundary

ParaGraph may claim comprehensive validation for the supported local baseline
only when clean CI, Browser E2E, launcher evidence, Tier 0–2, deterministic
local integrations, persistence/restart behavior, and safety regressions all
agree on the same candidate revision. A stronger all-integrations claim also
requires successful evidence for every advertised provider, database, and
remote vector adapter. Any unavailable service remains a named blocker.
