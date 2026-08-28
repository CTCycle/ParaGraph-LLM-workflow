# Runtime Modes
Last updated: 2026-07-11

## Supported Modes
### Local Launcher Mode
- Primary Windows mode.
- Uses `start_on_windows.ps1` to bootstrap portable runtimes, synchronize dependencies, build the frontend, and run the backend and frontend preview.
- Frontend runs from Vite preview and the backend runs with uvicorn.

### Manual Development Mode
- Backend and frontend are started separately for development control.
- Backend runs as a FastAPI and uvicorn process.
- Frontend runs through `npm run dev` or the related preview and build scripts.

### Containerized Mode
- No Docker or container runtime is implemented in this repository at present.
