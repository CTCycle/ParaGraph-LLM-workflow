You are working on the ParaGraph-LLM-workflow repository checked out at the current directory.

TASK: Remove all Tauri packaging infrastructure, consolidate the launcher scripts into a single PowerShell menu, and update all documentation. Do NOT modify any Python, TypeScript, or Angular source code.

## Step 1: Create `app.ps1` at repo root

Replace both `start_on_windows.bat` and `setup_and_maintenance.bat` with a single `app.ps1` interactive menu.

Menu title: "ParaGraph — LLM Workflow"

The menu options and logic are identical to the description in PROMPT 1 (DILIGENT) Step 1. Read the existing start_on_windows.bat and setup_and_maintenance.bat in this repo for the exact paths and defaults used.

## Step 2: Delete old batch files

Remove from repo root:
- start_on_windows.bat
- setup_and_maintenance.bat

## Step 3: Delete all Tauri / Cargo / Rust artifacts

Directories to delete (entire trees):
- app/src-tauri/ (Cargo.toml, Cargo.lock, build.rs, capabilities/, icons/, src/, tauri.conf.json)
- release/tauri/
- release/windows/ (if exists)

Files to delete:
- .github/workflows/desktop-release.yml

## Step 4: Update .gitignore

Remove entries for Tauri build outputs.

## Step 5: Update package.json (app/client/)

- Remove "@tauri-apps/cli" from devDependencies if present
- Remove any "build:tauri" script

## Step 6: Update README.md

Read the current README.md and make these changes:
- Remove the "## Packaging" section entirely (lines about desktop application through Tauri build flow)
- Remove the paragraph about app/src-tauri being versioned desktop source
- Remove the note about ignoring generated desktop outputs
- Remove any desktop/packaging badges
- Update all batch file references (start_on_windows.bat -> app.ps1)
- Simplify the description to only cover local webapp mode

## Step 7: Update assets/docs/

Scan for Tauri/desktop/packaging references and update.

## Step 8: Verify

Check: all Tauri artifacts removed, app.ps1 created, docs updated.