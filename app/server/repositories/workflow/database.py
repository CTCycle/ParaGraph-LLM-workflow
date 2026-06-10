from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import (
    URL,
    MetaData,
    Table,
    create_engine,
    delete,
    inspect,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from server.domain.node_handler_ingestion import normalize_database_engine
from server.domain.workflow_payloads import DatabaseConnectionHandle

###############################################################################
def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default

###############################################################################
def _resolve_local_path(path_value: str) -> Path:
    return Path(path_value).expanduser().resolve()

###############################################################################
def build_database_url(payload: dict[str, Any]) -> tuple[str | URL, dict[str, Any]]:
    engine = normalize_database_engine(payload.get("engine"), label="engine")
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    if engine == "sqlite":
        file_path = str(payload.get("file_path") or "").strip()
        if not file_path:
            raise ValueError("sqlite connections require file_path")
        resolved_file = _resolve_local_path(file_path)
        if not resolved_file.exists() or not resolved_file.is_file():
            raise ValueError(f"SQLite database file not found: {resolved_file}")
        return f"sqlite:///{resolved_file.as_posix()}", {}

    database_name = str(payload.get("database_name") or "").strip()
    host = str(payload.get("host") or "").strip()
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    port = payload.get("port")
    if not database_name or not host or not username or port is None:
        raise ValueError(
            f"{engine} connections require host, database_name, username, and port"
        )

    query = {
        str(key): str(value)
        for key, value in options.items()
        if key != "connect_timeout_s"
    }
    driver = "postgresql+psycopg" if engine == "postgresql" else "mysql+pymysql"
    return (
        URL.create(
            driver,
            username=username,
            password=password or None,
            host=host,
            port=int(port),
            database=database_name,
            query=query,
        ),
        {
            "connect_timeout": _coerce_int(
                payload.get("connect_timeout_s", options.get("connect_timeout_s")), 5
            )
        },
    )

###############################################################################
def build_engine_from_connection(connection: dict[str, Any]) -> Engine:
    handle = DatabaseConnectionHandle.model_validate(connection)
    database_url, connect_args = build_database_url(handle.model_dump(mode="json"))
    return create_engine(
        database_url, future=True, pool_pre_ping=True, connect_args=connect_args
    )

###############################################################################
def validate_connection(connection: dict[str, Any]) -> None:
    engine = build_engine_from_connection(connection)
    try:
        with Session(engine) as db_session:
            db_session.execute(select(1)).scalar_one()
    except SQLAlchemyError as exc:
        raise ValueError(f"Failed to connect to database: {exc}") from exc
    finally:
        engine.dispose()

###############################################################################
def inspect_database_schema(connection: dict[str, Any]) -> dict[str, Any]:
    engine = build_engine_from_connection(connection)
    try:
        inspector = inspect(engine)
        tables: list[dict[str, Any]] = []
        for table_name in inspector.get_table_names():
            primary_key = inspector.get_pk_constraint(table_name) or {}
            foreign_keys = inspector.get_foreign_keys(table_name) or []
            indexes = inspector.get_indexes(table_name) or []
            tables.append(
                {
                    "name": table_name,
                    "columns": [
                        {
                            "name": str(column.get("name") or ""),
                            "type": str(column.get("type") or ""),
                            "nullable": bool(column.get("nullable", True)),
                            "default": column.get("default"),
                            "primary_key": str(column.get("name") or "")
                            in set(primary_key.get("constrained_columns") or []),
                        }
                        for column in inspector.get_columns(table_name)
                    ],
                    "primary_key": {
                        "name": primary_key.get("name"),
                        "columns": primary_key.get("constrained_columns") or [],
                    },
                    "foreign_keys": [
                        {
                            "name": foreign_key.get("name"),
                            "columns": foreign_key.get("constrained_columns") or [],
                            "referred_table": foreign_key.get("referred_table"),
                            "referred_columns": foreign_key.get("referred_columns")
                            or [],
                        }
                        for foreign_key in foreign_keys
                    ],
                    "indexes": [
                        {
                            "name": index.get("name"),
                            "columns": index.get("column_names") or [],
                            "unique": bool(index.get("unique", False)),
                        }
                        for index in indexes
                    ],
                }
            )
        return {"tables": tables}
    except SQLAlchemyError as exc:
        raise ValueError(f"Failed to inspect database schema: {exc}") from exc
    finally:
        engine.dispose()

###############################################################################
def _load_table(engine: Engine, table_name: str) -> Table:
    metadata = MetaData()
    try:
        return Table(table_name, metadata, autoload_with=engine)
    except SQLAlchemyError as exc:
        raise ValueError(f"Failed to load table '{table_name}': {exc}") from exc

###############################################################################
def _validate_columns(table: Table, names: list[str] | set[str], label: str) -> None:
    missing = sorted(name for name in names if name not in table.c)
    if missing:
        raise ValueError(f"Unknown {label} column(s): {', '.join(missing)}")

###############################################################################
def _apply_filters(statement: Any, table: Table, filters: dict[str, Any]) -> Any:
    _validate_columns(table, set(filters), "filter")
    for column_name, value in filters.items():
        statement = statement.where(table.c[column_name] == value)
    return statement

###############################################################################
def _rows_dataset(
    *,
    operation: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    affected_rows: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "operation": operation,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
    }
    if affected_rows is not None:
        payload["affected_rows"] = affected_rows
    return payload

###############################################################################
def execute_create(
    connection: dict[str, Any], *, table_name: str, values: dict[str, Any]
) -> dict[str, Any]:
    if not values:
        raise ValueError("values must include at least one column")
    engine = build_engine_from_connection(connection)
    try:
        table = _load_table(engine, table_name)
        _validate_columns(table, set(values), "value")
        with engine.begin() as db_connection:
            result = db_connection.execute(insert(table).values(**values))
        return _rows_dataset(
            operation="create",
            columns=[],
            rows=[],
            affected_rows=int(result.rowcount or 0),
        )
    except SQLAlchemyError as exc:
        raise ValueError(f"Create operation failed: {exc}") from exc
    finally:
        engine.dispose()

###############################################################################
def execute_read(
    connection: dict[str, Any],
    *,
    table_name: str,
    columns: list[str],
    filters: dict[str, Any],
    limit: int,
    order_by: str,
) -> dict[str, Any]:
    engine = build_engine_from_connection(connection)
    try:
        table = _load_table(engine, table_name)
        selected_columns = columns or [column.name for column in table.columns]
        _validate_columns(table, selected_columns, "selected")
        statement = select(*(table.c[name] for name in selected_columns))
        statement = _apply_filters(statement, table, filters)
        if order_by.strip():
            _validate_columns(table, [order_by.strip()], "order_by")
            statement = statement.order_by(table.c[order_by.strip()])
        statement = statement.limit(limit)
        with Session(engine) as db_session:
            rows = [dict(row) for row in db_session.execute(statement).mappings()]
        return _rows_dataset(operation="read", columns=selected_columns, rows=rows)
    except SQLAlchemyError as exc:
        raise ValueError(f"Read operation failed: {exc}") from exc
    finally:
        engine.dispose()

###############################################################################
def execute_update(
    connection: dict[str, Any],
    *,
    table_name: str,
    values: dict[str, Any],
    filters: dict[str, Any],
) -> dict[str, Any]:
    if not values:
        raise ValueError("values must include at least one column")
    if not filters:
        raise ValueError("filters are required for update operations")
    engine = build_engine_from_connection(connection)
    try:
        table = _load_table(engine, table_name)
        _validate_columns(table, set(values), "value")
        statement = _apply_filters(update(table).values(**values), table, filters)
        with engine.begin() as db_connection:
            result = db_connection.execute(statement)
        return _rows_dataset(
            operation="update",
            columns=[],
            rows=[],
            affected_rows=int(result.rowcount or 0),
        )
    except SQLAlchemyError as exc:
        raise ValueError(f"Update operation failed: {exc}") from exc
    finally:
        engine.dispose()

###############################################################################
def execute_delete(
    connection: dict[str, Any], *, table_name: str, filters: dict[str, Any]
) -> dict[str, Any]:
    if not filters:
        raise ValueError("filters are required for delete operations")
    engine = build_engine_from_connection(connection)
    try:
        table = _load_table(engine, table_name)
        statement = _apply_filters(delete(table), table, filters)
        with engine.begin() as db_connection:
            result = db_connection.execute(statement)
        return _rows_dataset(
            operation="delete",
            columns=[],
            rows=[],
            affected_rows=int(result.rowcount or 0),
        )
    except SQLAlchemyError as exc:
        raise ValueError(f"Delete operation failed: {exc}") from exc
    finally:
        engine.dispose()

###############################################################################
def execute_custom_sql(connection: dict[str, Any], *, sql: str) -> dict[str, Any]:
    engine = build_engine_from_connection(connection)
    try:
        with engine.begin() as db_connection:
            result = db_connection.execute(text(sql))
            if result.returns_rows:
                rows = [dict(row) for row in result.mappings()]
                columns = list(result.keys())
                return _rows_dataset(operation="custom_sql", columns=columns, rows=rows)
            return _rows_dataset(
                operation="custom_sql",
                columns=[],
                rows=[],
                affected_rows=int(result.rowcount or 0),
            )
    except SQLAlchemyError as exc:
        raise ValueError(f"SQL query failed: {exc}") from exc
    finally:
        engine.dispose()
