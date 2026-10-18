# Validation Strategy
Last updated: 2026-10-18

## Purpose
This document defines the ParaGraph validation campaign and the evidence standard. The [project status ledger](../project_status_ledger.md) is the sole record of current outcomes and durable validation evidence. Reproducible checks belong in the tracked backend, frontend, and browser test suites.

A result applies only to its recorded revision, environment, service, scenario, and workflow path. Source inspection, a test's existence, or mocked behavior alone does not establish a product pass. Backend checks do not establish browser behavior; local deterministic runs do not establish provider or external-service behavior.

## Campaign Tiers

| Tier | Focus | Slice IDs | Exit signal |
| --- | --- | --- | --- |
| 0 | Clean CI, Windows bootstrap, launcher lifecycle, and evidence integrity | PG-T0-01–PG-T0-04 | A reproducible baseline exists with no unresolved Tier 0 failure. |
| 1 | Routes, API contract, configuration and secrets, browser graph persistence, and SQLite application persistence | PG-T1-01–PG-T1-05 | Foundation flows have current evidence. |
| 2 | Node catalog and templates, graph editing, compiler, deterministic execution, lifecycle controls, restart, and event replay | PG-T2-01–PG-T2-08 | Core workflows have browser and durable-state evidence. |
| 3 | Local node families, documents, structured data, retrieval, uploads, databases, vectors, HTTP, and tools | PG-T3-01–PG-T3-11 | Each claimed local capability has representative runtime evidence. |
| 4 | Provider model management and execution, external providers, and Chat history | PG-T4-01–PG-T4-05 | Provider success and controlled failure are reported per provider. |
| 5 | Malformed input, transport and security limits, destructive launcher actions, accessibility, guidance, and performance | PG-T5-01–PG-T5-05 | Resilience and safety claims have direct evidence. |

Recommended order: Tier 0, Tier 1, Tier 2, deterministic local Tier 3, external/provider paths, then Tier 5. An unavailable service remains blocked; a mock or a different provider cannot substitute for it.

## Slice and Evidence Rules
- Slice identifiers are stable. Update the existing ledger entry when a slice is rerun; do not create a parallel history.
- Record scope, status, tested revision and date, environment, executed scenario, and the evidence link or tracked test path.
- State out-of-scope behavior, remaining gaps, and external prerequisites. A PASS covers only its stated scope.
- Use PASS, PARTIAL, FAIL, BLOCKED, or UNTESTED for campaign outcomes. Keep coverage gaps in validation debt and confirmed defects in Open Issues.
- Record a meaningful failure class when applicable: FUNC, FE, BE, INT, STATE, PERF, UX, CFG, or ENV.
- Follow inspect → execute → observe → diagnose → fix → retest → adjacent regression → record. After a fix, run the affected scenario and its smallest adjacent regression.
- Store transient screenshots, databases, exports, and logs in ignored scratch areas. The ledger must retain the durable claim without depending on a scratch artifact.

## Completion Boundary
Comprehensive validation of the supported local baseline requires clean CI, browser E2E, launcher evidence, Tier 0–2, representative deterministic local integrations, persistence and restart coverage, and safety regressions on the same candidate revision.

An all-integrations claim also requires successful evidence for each advertised provider, database, and remote vector adapter. Keep each unavailable service and each untested capability explicit.
