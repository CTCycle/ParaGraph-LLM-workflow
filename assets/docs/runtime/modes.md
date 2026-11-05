# Runtime Modes
Last updated: 2026-11-05

## Supported Modes
### Local Launcher Mode
- Primary Windows mode.
- Uses start_on_windows.bat, which invokes setup_and_maintenance.ps1 -Launch to bootstrap portable runtimes, repair missing dependencies, validate the frontend build fingerprint, and run one uvicorn process.
- The backend serves the built frontend, the `/api` path, and the execution WebSocket from a single origin (`FASTAPI_HOST:FASTAPI_PORT`); no Vite server runs.
- Steady-state launch reuses a current fingerprinted build. Maintenance option 2 installs or updates dependencies and rebuilds; option 3 is the explicit unconditional frontend rebuild path.
- Launch mode asks before terminating a process that occupies the backend port. Option 1 remains the explicit broad application-process cleanup operation.

### Manual Development Mode
- Backend and frontend are started separately for development control.
- Backend runs as a FastAPI and uvicorn process.
- Frontend runs through `npm run dev` (Vite dev server with proxy to the backend). `npm run preview` is test tooling only, not a production server.

### Containerized Mode
- No Docker or container runtime is implemented in this repository at present.
