# Curated QA Evidence

This directory is the durable evidence layer for the validation ledger. Curated
reports and the screenshots they reference are revision-scoped and may be
linked from `assets/docs/project_status_ledger.md` or a validation strategy
document.

The repository ignores `assets/QA/**` by default because the local directory
also contains generated pytest fixtures, caches, temporary databases, and
provider/model artifacts. Only reviewed, sanitized evidence is force-added to
the remote. Never commit credentials, raw user data, disposable databases, or
bulk test output.

Current curated reports:

- [`PG-T0-01-6a9e5e1.md`](PG-T0-01-6a9e5e1.md) — clean-CI baseline failure and
  minimal remediation record.
- [`PG-T0-02-f43590f.md`](PG-T0-02-f43590f.md) — fresh Windows bootstrap,
  repeat setup, migration idempotence, and incompatible-schema preservation.
- [`PG-T0-03-3de7520.md`](PG-T0-03-3de7520.md) — launcher safety-race harness
  and a live approved-conflict attempt blocked by Windows process termination.
- [`PG-T0-03-3010c00.md`](PG-T0-03-3010c00.md) — build-fingerprint matrix
  passed; option 1 reached both health endpoints but Windows blocked browser
  launch and process cleanup, so warm-start timings remain unvalidated.
- [`PG-T1-01-c17d740.md`](PG-T1-01-c17d740.md) — current provider and
  configuration route behavior, including the update-order regression fix.
- [`PG-T1-02-c17d740.md`](PG-T1-02-c17d740.md) — current OpenAPI and generated
  frontend API contract alignment.
- [`PG-T1-03-c17d740.md`](PG-T1-03-c17d740.md) — disposable SQLite
  configuration/profile persistence and secret-redaction validation.
- [`paragraph-e2e-system-validation-2026-08-26.md`](paragraph-e2e-system-validation-2026-08-26.md)
  — live full-stack validation and known provider blockers.
- [`paragraph_e2e_validation_2026-08-02.md`](paragraph_e2e_validation_2026-08-02.md)
  — earlier UI/system validation.
- [`guidance-validation.md`](guidance-validation.md) — contextual guidance
  browser and visual evidence.

New slice reports should use the stable slice ID and tested revision, for
example `PG-T1-01-<short-sha>.md`, and should be linked from the status ledger.
