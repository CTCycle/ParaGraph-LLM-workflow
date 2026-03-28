# README Writing Guidelines

Use this structure for repository-level README updates.

## 1. Scope and Audience

- Write for users/operators first.
- Explain capabilities and usage flow, not internal implementation details.
- Keep wording factual and current with code.

## 2. Required Sections

1. Project Overview
2. Installation
3. Usage
4. Testing
5. Configuration
6. Resources/Storage
7. Maintenance Scripts
8. License

If a section does not apply, omit it cleanly.

## 3. ParaGraph-Specific Requirements

README content must stay aligned with:

- Active API families: `/workflows`, `/executions`, `/nodes`, `/providers`, `/configurations`
- Runtime launch flow: `ParaGraph/start_on_windows.bat`
- Test runner: `tests/run_tests.bat`
- Runtime environment: `runtimes/.venv`, `ParaGraph/settings/.env`, `ParaGraph/settings/.env.local.example`
- Resource directories under `ParaGraph/resources`

## 4. Installation Guidance

- Prefer minimal, reproducible commands.
- Separate Windows launcher flow from manual setup flow.
- State first-run behavior (runtime/toolchain bootstrap) vs subsequent runs.

## 5. Usage Guidance

- Document the user workflow:
  - configure runtime/provider
  - build/edit workflow
  - compile and run
  - inspect outputs/events
- Include screenshots only when they exist and are current.

## 6. Configuration Section Rules

Include a variable table:

| Variable | Description |
| --- | --- |
| `NAME` | purpose + default/source |

Prioritize keys used by current runtime paths (`FASTAPI_*`, `UI_*`, `VITE_API_BASE_URL`, deployment mode, DB settings, provider keys).

## 7. Maintenance Section Rules

List scripts and outcomes (not internals), for example:

- `ParaGraph/setup_and_maintenance.bat`
- `tests/run_tests.bat`

## 8. Quality Checks Before Finalizing README

- Verify commands exist and run paths are correct.
- Verify endpoint names match actual routers.
- Remove stale references to retired routes/features.
