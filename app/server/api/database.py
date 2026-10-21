from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.contracts.database import (
    DatabaseConfigurationPayload,
    DatabaseConfigurationResponse,
    DatabaseTestResponse,
)
from server.repositories.database.configuration import (
    DatabaseConfiguration,
    DatabaseConfigurationError,
)
from server.repositories.database.runtime import (
    DatabaseBusyError,
    database_runtime,
)


router = APIRouter(prefix="/database", tags=["database"])


###############################################################################
def _configuration_response() -> DatabaseConfigurationResponse:
    status = database_runtime.status()
    configured = status.get("configuration") or {}
    return DatabaseConfigurationResponse(
        backend=configured.get("backend", "sqlite"),
        database_path=configured.get("database_path", "database.db"),
        insert_batch_size=configured.get("insert_batch_size", 1000),
        resolved_path=status.get("database_path"),
        connected=bool(status.get("connected")),
        error=status.get("error"),
    )


###############################################################################
@router.get("/configuration", response_model=DatabaseConfigurationResponse)
def get_database_configuration() -> DatabaseConfigurationResponse:
    return _configuration_response()


###############################################################################
@router.post("/test", response_model=DatabaseTestResponse)
def test_database_configuration(
    payload: DatabaseConfigurationPayload,
) -> DatabaseTestResponse:
    try:
        database_runtime.test(DatabaseConfiguration.model_validate(payload.model_dump()))
    except DatabaseConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DatabaseTestResponse(
        ok=True,
        message="SQLite connection is available. Applying may initialize or upgrade its application schema.",
    )


###############################################################################
@router.put("/configuration", response_model=DatabaseConfigurationResponse)
def put_database_configuration(
    payload: DatabaseConfigurationPayload,
) -> DatabaseConfigurationResponse:
    try:
        database_runtime.activate(DatabaseConfiguration.model_validate(payload.model_dump()))
    except DatabaseBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database change was not applied: {exc}") from exc
    return _configuration_response()
