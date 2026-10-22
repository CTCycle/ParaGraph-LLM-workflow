from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version as package_version

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse

from server.common import path as common_path
from server.common.constants import FASTAPI_DESCRIPTION, FASTAPI_TITLE
from server.api.client_hosting import ClientHostingMiddleware
from server.api.chat_history import router as chat_history_router
from server.api.configurations import router as configurations_router
from server.api.database import router as database_router
from server.api.executions import router as executions_router
from server.api.nodes import router as nodes_router
from server.api.providers import router as providers_router
from server.api.request_id import request_id_middleware
from server.api.workflow_templates import router as workflow_templates_router
from server.api.ws import router as ws_router
from server.common.utils.logger import logger
from server.configurations.startup import get_configuration_runtime, get_server_settings
from server.repositories.database.initializer import initialize_database
from server.repositories.database.runtime import DatabaseUnavailableError
from server.repositories.workflow.execution_run import execution_run_repository
from server.repositories.workflow.database import reset_database_engines
from server.services.startup_validation import run_startup_validations
from server.services.workflow.execution import execution_service

APP_VERSION = package_version("paragraph")

###############################################################################
def _client_build_available() -> bool:
    return (common_path.FRONTEND_DIST_ROOT / "index.html").is_file()

###############################################################################
def redirect_root_to_docs() -> RedirectResponse:
    return RedirectResponse("/docs")

###############################################################################
def _parse_csv_setting(value: str | None, default: tuple[str, ...]) -> list[str]:
    if value is None or not value.strip():
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]

###############################################################################
@asynccontextmanager
async def app_lifespan(application: FastAPI) -> AsyncIterator[None]:
    try:
        initialize_database()
        settings = get_server_settings()
        execution_run_repository.cleanup_retention(settings.jobs.retention_days)
        run_startup_validations()
        execution_service.recover_interrupted()
    except Exception:
        # Keep the Settings UI available so a broken/missing target can be repaired.
        logger.exception(
            "Application startup failed; database configuration remains available for recovery"
        )
        settings = get_server_settings()
    application.state.server_settings = settings
    try:
        yield
    finally:
        from server.services.jobs import job_manager

        job_manager.shutdown()
        reset_database_engines()

###############################################################################
def create_app() -> FastAPI:
    app = FastAPI(
        title=FASTAPI_TITLE,
        version=APP_VERSION,
        description=FASTAPI_DESCRIPTION,
        lifespan=app_lifespan,
    )

    app.middleware("http")(request_id_middleware)

    environment = get_configuration_runtime().environment()
    cors_origins = _parse_csv_setting(environment.get("CORS_ALLOWED_ORIGINS"), ())
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=environment.get_bool("CORS_ALLOW_CREDENTIALS", False),
            allow_methods=_parse_csv_setting(
                environment.get("CORS_ALLOWED_METHODS"), ("*",)
            ),
            allow_headers=_parse_csv_setting(
                environment.get("CORS_ALLOWED_HEADERS"), ("*",)
            ),
        )

    @app.exception_handler(DatabaseUnavailableError)
    async def database_unavailable_handler(
        _request: Request, exc: DatabaseUnavailableError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    app.include_router(workflow_templates_router)
    app.include_router(executions_router)
    app.include_router(nodes_router)
    app.include_router(providers_router)
    app.include_router(configurations_router)
    app.include_router(database_router)
    app.include_router(chat_history_router)
    app.include_router(ws_router)

    if _client_build_available():
        app.add_middleware(
            ClientHostingMiddleware,
            api_base=environment.get("VITE_API_BASE_URL") or "",
            client_root=common_path.FRONTEND_DIST_ROOT,
        )
        return app

    app.add_api_route(
        "/", redirect_root_to_docs, methods=["GET"], include_in_schema=False
    )
    return app


app = create_app()
