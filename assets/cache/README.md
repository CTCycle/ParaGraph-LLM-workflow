# Developer cache

Local developer caches and generated test/build artifacts belong under this directory. The repository configuration routes
pytest, Ruff, Python bytecode, coverage, uv, npm, Vite, Vitest, Playwright, and the frontend build output here.

The backend virtual environment and frontend `node_modules` remain beside their projects because the installed runtimes
expect those locations. They are dependencies, not caches or generated test/build output.
