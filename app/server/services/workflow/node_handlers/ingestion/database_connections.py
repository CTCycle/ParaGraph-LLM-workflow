from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from server.contracts.node_handler_ingestion import (
    DatabaseConnectionParameters,
    SQLDatabaseParameters,
    SQLFileDatabaseParameters,
)
from server.repositories.workflow.database import (
    build_database_url,
    register_database_credential,
)
from server.services.configuration import configuration_service
from server.services.workflow.node_handlers.ingestion.files import resolve_local_path


###############################################################################
def _build_sql_connection_options(*, db_ssl: bool, db_ssl_ca: str) -> dict[str, Any]:
    options: dict[str, Any] = {}
    if db_ssl:
        options["ssl"] = "true"
        if db_ssl_ca.strip():
            options["ssl_ca"] = db_ssl_ca.strip()
    return options


###############################################################################
def _validate_and_build_database_connection(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    parsed = DatabaseConnectionParameters.model_validate(parameters)
    database_url, connect_args = build_database_url(parsed.model_dump(mode="json"))
    engine = create_engine(
        database_url, future=True, pool_pre_ping=True, connect_args=connect_args
    )
    try:
        with Session(engine) as db_session:
            db_session.execute(select(1)).scalar_one()
    except SQLAlchemyError as exc:
        raise ValueError(f"Failed to connect to database: {exc}") from exc
    finally:
        engine.dispose()

    resolved_file_path = (
        str(resolve_local_path(parsed.file_path)) if parsed.engine == "sqlite" else None
    )
    return {
        "connection": {
            "engine": parsed.engine,
            "database_name": parsed.database_name
            or (Path(resolved_file_path).stem if resolved_file_path else None),
            "host": parsed.host or None,
            "port": parsed.port,
            "username": parsed.username or None,
            "credential_ref": parsed.credential_ref or None,
            "file_path": resolved_file_path,
            "read_only": False,
            "options": {
                **parsed.options,
                "connect_timeout_s": parsed.connect_timeout_s,
            },
        }
    }


###############################################################################
def _sql_database_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    parsed = SQLDatabaseParameters.model_validate(parameters)
    provider_configuration = configuration_service.resolve_provider_configuration(
        profile_name=parsed.credential_profile,
        provider=parsed.db_engine,
    )
    credential_ref = register_database_credential(provider_configuration.api_key or "")
    connection_payload = {
        "engine": parsed.db_engine,
        "database_name": parsed.db_name,
        "host": parsed.db_host,
        "port": parsed.db_port,
        "username": parsed.db_user,
        "credential_ref": credential_ref,
        "file_path": "",
        "options": _build_sql_connection_options(
            db_ssl=parsed.db_ssl, db_ssl_ca=parsed.db_ssl_ca
        ),
        "connect_timeout_s": parsed.db_connect_timeout,
    }
    return _validate_and_build_database_connection(connection_payload)


###############################################################################
def _sql_file_database_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    parsed = SQLFileDatabaseParameters.model_validate(parameters)
    connection_payload = {
        "engine": "sqlite",
        "database_name": "",
        "host": "",
        "port": None,
        "username": "",
        "credential_ref": "",
        "file_path": parsed.db_path,
        "options": {},
        "connect_timeout_s": parsed.db_connect_timeout,
    }
    return _validate_and_build_database_connection(connection_payload)


__all__ = ["_sql_database_executor", "_sql_file_database_executor"]
