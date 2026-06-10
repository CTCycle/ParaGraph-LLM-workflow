# Runtime Modes
Last updated: 2026-06-02

## Supported Modes
### Local Launcher Mode
- Primary Windows mode.
- Uses `start_on_windows.bat` to bootstrap portable runtimes, synchronize Python dependencies, build or serve the frontend, and run the backend.
- Frontend runs from Vite preview and the backend runs with uvicorn.

### Manual Development Mode
- Backend and frontend are started separately for development control.
- Backend runs as a FastAPI and uvicorn process.
- Frontend runs through `npm run dev` or the related preview and build scripts.

### Desktop Packaged Mode
- Implemented in `app/src-tauri`.
- The desktop app boots the backend runtime internally and then loads the web UI in a Tauri window.
- Release packaging is driven by `release/tauri/build_with_tauri.bat` and npm Tauri scripts.

### Containerized Mode
- No Docker or container runtime is implemented in this repository at present.
