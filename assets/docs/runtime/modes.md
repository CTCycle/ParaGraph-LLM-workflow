# Runtime Modes
Last updated: 2026-09-22

## Supported Modes
### Local Launcher Mode
- Primary Windows mode.
- Uses `start_on_windows.ps1` to bootstrap portable runtimes, repair missing dependencies, validate the frontend build fingerprint, and run the backend and frontend preview.
- Frontend runs from Vite preview and the backend runs with uvicorn.
- Steady-state option `1` reuses a current fingerprinted build. Option `3` installs or updates dependencies and rebuilds; option `4` is the explicit unconditional frontend rebuild path.
- Option `1` asks before terminating processes that occupy configured ports. Option `2` remains the explicit broad application-process cleanup operation.

### Manual Development Mode
- Backend and frontend are started separately for development control.
- Backend runs as a FastAPI and uvicorn process.
- Frontend runs through `npm run dev` or the related preview and build scripts.

### Containerized Mode
- No Docker or container runtime is implemented in this repository at present.
