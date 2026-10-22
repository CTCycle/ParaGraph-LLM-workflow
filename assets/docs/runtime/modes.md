# Runtime Modes
Last updated: 2026-10-22

## Supported Modes
### Local Launcher Mode
- Primary Windows mode.
- Uses `start_on_windows.ps1` to bootstrap portable runtimes, repair missing dependencies, validate the frontend build fingerprint, and run one uvicorn process.
- The backend serves the built frontend, the `/api` path, and the execution WebSocket from a single origin (`FASTAPI_HOST:FASTAPI_PORT`); no Vite server runs.
- Steady-state option `1` reuses a current fingerprinted build. Option `3` installs or updates dependencies and rebuilds; option `4` is the explicit unconditional frontend rebuild path.
- Option `1` asks before terminating a process that occupies the backend port. Option `2` remains the explicit broad application-process cleanup operation.

### Manual Development Mode
- Backend and frontend are started separately for development control.
- Backend runs as a FastAPI and uvicorn process.
- Frontend runs through `npm run dev` (Vite dev server with proxy to the backend). `npm run preview` is test tooling only, not a production server.

### Containerized Mode
- No Docker or container runtime is implemented in this repository at present.
