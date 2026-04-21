from __future__ import annotations

import os
import warnings
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ParaGraph.server.common.constants import (
    FASTAPI_DESCRIPTION,
    FASTAPI_TITLE,
    FASTAPI_VERSION,
)
from ParaGraph.server.common.security import is_cloud_deployment
from ParaGraph.server.api.configurations import router as configurations_router
from ParaGraph.server.api.executions import router as executions_router
from ParaGraph.server.api.nodes import router as nodes_router
from ParaGraph.server.api.providers import router as providers_router
from ParaGraph.server.api.root import router as root_router
from ParaGraph.server.api.workflows import router as workflows_router
from ParaGraph.server.api.ws import router as ws_router

warnings.filterwarnings("ignore", category=FutureWarning)


def create_app() -> FastAPI:
    cloud_mode = is_cloud_deployment()
    tauri_mode = os.getenv("PARAGRAPH_TAURI_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    frontend_dist = Path(__file__).resolve().parents[1] / "client" / "dist"

    app = FastAPI(
        title=FASTAPI_TITLE,
        version=FASTAPI_VERSION,
        description=FASTAPI_DESCRIPTION,
        docs_url=None if cloud_mode else "/docs",
        redoc_url=None if cloud_mode else "/redoc",
        openapi_url=None if cloud_mode else "/openapi.json",
    )

    app.state.cloud_mode = cloud_mode
    app.state.tauri_mode = tauri_mode

    app.include_router(workflows_router)
    app.include_router(executions_router)
    app.include_router(nodes_router)
    app.include_router(providers_router)
    app.include_router(configurations_router)
    app.include_router(ws_router)

    if tauri_mode and frontend_dist.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(frontend_dist), html=True),
            name="paragraph-ui",
        )
        return app

    app.include_router(root_router)
    return app


app = create_app()
