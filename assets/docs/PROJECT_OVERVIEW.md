# PROJECT_OVERVIEW

Last updated: 2026-05-09

## FILES INDEX

- PROJECT_OVERVIEW.md  
  Master index and operating rules for documentation maintenance and Windows environment expectations.
- ARCHITECTURE.md  
  System architecture reference: directory layout, entry points, API surface, layers, persistence, and concurrency model.
- CODING_RULES.md  
  Consolidated coding standards for Python and TypeScript used in this repository.
- RUNTIME_MODES.md  
  Supported runtime targets, startup procedures, configuration differences, interoperability, and deployment constraints.
- UI_STANDARDS.md  
  Enforceable UI system definition based on the implemented React/CSS frontend.
- NODES_LIBRARY.md  
  Node catalog and manifest reference, including custom node import, runtime integration, vector collections, metadata, tokenizer, and provider-neutral tool calling.
- USER_MANUAL.md  
  End-user operational guide for launching, configuring, building workflows, and troubleshooting.

## CONTEXT RULES

- Read documentation files only when needed to complete the current task.
- Defer deep documentation reads until code context proves they are required.
- Keep all docs in `assets/docs` updated when architecture, runtime, or UI behavior changes.
- Always add or refresh a `Last updated: YYYY-MM-DD` line when modifying a document.
- Do not read all `SKILL.md` files indiscriminately.
- Pre-select relevant docs from folder structure and user intent before opening files.

## ENVIRONMENT RULES

- Assume Windows as the default operating environment for commands, scripts, and troubleshooting.
- Provide equivalent command guidance for both CMD (`.bat`, `copy`, `set`) and PowerShell (`Get-ChildItem`, `$env:...`) when relevant.
- Keep runtime instructions aligned with project launch scripts (`start_on_windows.bat`, `release\\tauri\\build_with_tauri.bat`).
- Update this section whenever new Windows-specific constraints, workarounds, or tooling patterns are identified.

