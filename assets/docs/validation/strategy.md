# Validation Strategy
Last updated: 2026-10-18

## Purpose and authority

This document is the durable campaign map for validating ParaGraph from its
clean baseline through provider-backed and resilience workflows.

- [`project_status_ledger.md`](../project_status_ledger.md) is the canonical
  record of current status and durable validation outcomes. Update it instead of
  creating standalone QA report files.
- Reproducible checks live in the tracked test suites: `app/tests` (pytest) and
  the frontend unit and `app/client/tests/e2e` suites.
- Source inspection, the existence of a test, a catalog mapping, or a mocked
  response is not a product `PASS` by itself.
- Claims are scoped to the exact revision, environment, provider/service, and
  workflow path recorded by the evidence. A deterministic local run does not
  validate a model provider, and a backend test does not validate browser UX.
- `assets/QA/` and `runtimes/cache/` are ignored scratch directories for
  transient artifacts (screenshots, run JSON, databases, logs). Never commit
  them, and never let them hold the only copy of a durable claim.

## Campaign tiers

Validation proceeds from cheap, deterministic foundations toward stateful and
external integrations. The slice IDs are stable so reruns can be compared
without rewriting the status ledger.

| Tier | Focus | Slice IDs | Exit signal |
| --- | --- | --- | --- |
| 0 | Clean CI, Windows bootstrap, launcher lifecycle, and evidence integrity | `PG-T0-01`–`PG-T0-04` | A reproducible baseline exists and no Tier 0 slice is an unresolved `FAIL`. |
| 1 | Routes, API boundary, configuration/secrets, browser-local workflow persistence, and SQLite application persistence | `PG-T1-01`–`PG-T1-05` | Foundation flows are exercised against the current candidate revision. |
| 2 | Node catalog/templates, custom import, graph editing, compiler diagnostics, deterministic execution, lifecycle controls, and restart/event replay | `PG-T2-01`–`PG-T2-08` | Core product workflows have browser and durable-state evidence. |
| 3 | Deterministic node families, documents/chunks, structured data, retrieval, uploads, local database/vector adapters, HTTP nodes, and tools | `PG-T3-01`–`PG-T3-11` | Each supported local capability family has representative runtime evidence. |
| 4 | Ollama/Hugging Face management and runtime, cloud/local provider execution, and Chat history | `PG-T4-01`–`PG-T4-05` | Provider-specific success and controlled-failure paths are reported separately. |
| 5 | Malformed input, transport/security limits, destructive launcher actions, accessibility/guidance, and performance | `PG-T5-01`–`PG-T5-05` | Resilience and safety claims have direct evidence with no unresolved critical regression. |

The recommended order is Tier 0, Tier 1, Tier 2, deterministic/local Tier 3,
provider/external Tier 4, and Tier 5 resilience. Provider availability must not
delay clean CI or deterministic foundations, and blocked external services must
remain explicitly `BLOCKED` rather than being converted into a mocked success
claim.

## Slice conventions

- Slice IDs follow `PG-T<tier>-<number>` (for example `PG-T3-01`) and are
  stable: reuse the ID and update the existing ledger row when a slice is rerun
  on a new revision.
- A slice is `PASS` only for its recorded scope. Record explicit out-of-scope
  behavior, remaining gaps, and external prerequisites rather than implying
  full coverage.
- Completed and partial slice scopes and outcomes are recorded in the campaign
  table in the [status ledger](../project_status_ledger.md); this document
  defines the tiers and the recording rules, not the history.
- Tier 0 details worth preserving for reruns: `PG-T0-01` runs backend
  lint/compile/tests plus frontend install/lint/build/unit on a clean checkout
  with the five explicit Vite build inputs (`FASTAPI_HOST`, `FASTAPI_PORT`,
  `UI_HOST`, `UI_PORT`, `VITE_API_BASE_URL`); `PG-T0-02` exercises launcher
  options 3 and 5 from a disposable data root with missing, empty, and
  incompatible databases (never real user data); `PG-T0-03` exercises official
  options 1 and 2 from no running processes, including a controlled port
  collision, without killing unrelated processes.

## Recording rules

Every validated or partially validated slice must state, in the ledger entry
and any supporting test change:

1. scope and explicit out-of-scope behavior;
2. exact planned and executed scenarios;
3. status: `PASS`, `PARTIAL`, `FAIL`, `BLOCKED`, or `UNTESTED`;
4. failure class when applicable: `FUNC`, `FE`, `BE`, `INT`, `STATE`, `PERF`,
   `UX`, `CFG`, or `ENV`;
5. tested revision, OS/runtime/browser/service versions, and date;
6. root cause, surgical fix, and adjacent regression results where applicable;
7. durable evidence: a tracked test path, a CI run URL, or a dated outcome
   statement in the ledger;
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
