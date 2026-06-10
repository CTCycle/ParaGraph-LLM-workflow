# Deployment
Last updated: 2026-06-03

## Packaging Targets
- Desktop packaging targets Tauri bundle output such as `msi`, `setup.exe`, and portable executables.
- Build orchestration is script-driven through `release/tauri/build_with_tauri.bat`.
- Exported artifacts are copied into:
  - `release/windows/installers`
  - `release/windows/portable`
- Portable exports keep the application executable at the top level and place the bundled runtime payload in a sibling `runtime/` folder.

## Limitations And Constraints
- Packaged desktop launcher logic is Windows-only in the current implementation.
- Long-running workflow execution uses background threads with poll and event-stream status updates.
- Runtime-heavy folders such as `release/windows`, `app/src-tauri/target`, and `app/client/node_modules` are operational artifacts, not source-of-truth code.

## Operational Guidance
- Treat packaged outputs as build artifacts rather than documentation or source inputs.
- Keep deployment notes aligned with the actual batch scripts and Tauri packaging configuration.
