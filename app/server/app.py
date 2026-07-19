from __future__ import annotations

import os
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from server.common import path as common_path
from server.common.constants import FASTAPI_DESCRIPTION, FASTAPI_TITLE, FASTAPI_VERSION
from server.api.configurations import router as configurations_router
from server.api.executions import router as executions_router
from server.api.nodes import router as nodes_router
from server.api.providers import router as providers_router
from server.api.request_id import request_id_middleware
from server.api.workflows import router as workflows_router
from server.api.ws import router as ws_router
from server.configurations.startup import get_server_settings
from server.repositories.database.initializer import initialize_database
from server.repositories.workflow.database import reset_database_engines
from server.services.startup_validation import run_startup_validations
from server.services.workflow.execution import execution_service

warnings.filterwarnings("ignore", category=FutureWarning)

###############################################################################
def _client_build_available() -> bool:
    return (common_path.FRONTEND_DIST_ROOT / "index.html").is_file()

###############################################################################
def _resolve_client_file(full_path: str) -> Path | None:
    client_root = common_path.FRONTEND_DIST_ROOT.resolve()
    requested_path = (client_root / full_path).resolve()

    if not requested_path.is_relative_to(client_root):
        return None

    if requested_path.is_file():
        return requested_path

    return None

###############################################################################
def serve_client_root() -> FileResponse:
    return FileResponse(common_path.FRONTEND_DIST_ROOT / "index.html")

###############################################################################
def serve_client_path(full_path: str) -> FileResponse:
    client_file = _resolve_client_file(full_path)
    if client_file is not None:
        return FileResponse(client_file)
    return FileResponse(common_path.FRONTEND_DIST_ROOT / "index.html")

###############################################################################
def redirect_root_to_docs() -> RedirectResponse:
    return RedirectResponse("/docs")

###############################################################################
@asynccontextmanager
async def app_lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_server_settings()
    initialize_database()
    run_startup_validations()
    execution_service.recover_interrupted()
    application.state.server_settings = settings
    try:
        yield
    finally:
        reset_database_engines()

###############################################################################
def create_app() -> FastAPI:
    tauri_mode = os.getenv("PARAGRAPH_TAURI_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    app = FastAPI(
        title=FASTAPI_TITLE,
        version=FASTAPI_VERSION,
        description=FASTAPI_DESCRIPTION,
        lifespan=app_lifespan,
    )

    app.state.tauri_mode = tauri_mode
    app.middleware("http")(request_id_middleware)

    app.include_router(workflows_router)
    app.include_router(executions_router)
    app.include_router(nodes_router)
    app.include_router(providers_router)
    app.include_router(configurations_router)
    app.include_router(ws_router)

    if tauri_mode and _client_build_available():
        if common_path.FRONTEND_ASSETS_ROOT.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(common_path.FRONTEND_ASSETS_ROOT)),
                name="paragraph-assets",
            )
        app.add_api_route(
            "/", serve_client_root, methods=["GET"], include_in_schema=False
        )
        app.add_api_route(
            "/{full_path:path}",
            serve_client_path,
            methods=["GET"],
            include_in_schema=False,
        )
        return app

    app.add_api_route(
        "/", redirect_root_to_docs, methods=["GET"], include_in_schema=False
    )
    return app


app = create_app()
