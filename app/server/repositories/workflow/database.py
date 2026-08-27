from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

from sqlalchemy import (
    URL,
    MetaData,
    Table,
    create_engine,
    delete,
    func,
    inspect,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from server.common.utils.values import coerce_int
from server.contracts.node_handler_ingestion import normalize_database_engine
from server.contracts.workflow_payloads import DatabaseConnectionHandle

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_READ_ONLY_SQL = re.compile(r"^\s*(select|with|explain|pragma)\b", re.IGNORECASE)
_MAX_BULK_ROWS = 1_000
_MAX_PAGE_SIZE = 1_000
_credential_lock = threading.Lock()
_credential_passwords: dict[str, str] = {}

###############################################################################
def register_database_credential(password: str) -> str:
    reference = uuid.uuid4().hex
    with _credential_lock:
        _credential_passwords[reference] = password
    return reference

###############################################################################
def _resolve_password(payload: dict[str, Any]) -> str:
    if "password" in payload:
        raise ValueError(
            "Database connections must use an opaque credential_ref"
        )
    reference = str(payload.get("credential_ref") or "")
    if not reference:
        raise ValueError(
            "Server database connections require an opaque credential_ref"
        )
    with _credential_lock:
        password = _credential_passwords.get(reference)
    if password is None:
        raise ValueError("Database credential reference is unavailable")
    return password

###############################################################################
def _resolve_local_path(path_value: str) -> Path:
    return Path(path_value).expanduser().resolve()

###############################################################################
def _validate_identifier(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not _IDENTIFIER.fullmatch(normalized):
        raise ValueError(f"Invalid {label}: {value!r}")
    return normalized

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
    password = _resolve_password(payload)
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
    return URL.create(
        driver,
        username=username,
        password=password or None,
        host=host,
        port=int(port),
        database=database_name,
        query=query,
    ), {
        "connect_timeout": coerce_int(
            payload.get("connect_timeout_s", options.get("connect_timeout_s")), 5
        )
    }

###############################################################################
class EngineRegistry:
    """Bounded engine cache whose opaque keys never contain credentials."""

    # -------------------------------------------------------------------------
    def __init__(self, max_size: int = 16) -> None:
        self.max_size = max_size
        self._engines: OrderedDict[str, Engine] = OrderedDict()
        self._lock = threading.Lock()

    # -------------------------------------------------------------------------
    @staticmethod
    def identity(connection: dict[str, Any]) -> str:
        handle = DatabaseConnectionHandle.model_validate(connection)
        payload = handle.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    # -------------------------------------------------------------------------
    def get(self, connection: dict[str, Any]) -> Engine:
        key = self.identity(connection)
        with self._lock:
            engine = self._engines.pop(key, None)
            if engine is not None:
                self._engines[key] = engine
                return engine
            url, connect_args = build_database_url(connection)
            engine = create_engine(
                url, future=True, pool_pre_ping=True, connect_args=connect_args
            )
            self._engines[key] = engine
            while len(self._engines) > self.max_size:
                self._engines.popitem(last=False)[1].dispose()
            return engine

    # -------------------------------------------------------------------------
    def dispose_all(self) -> None:
        with self._lock:
            engines = list(self._engines.values())
            self._engines.clear()
        for engine in engines:
            engine.dispose()

    # -------------------------------------------------------------------------
    def size(self) -> int:
        with self._lock:
            return len(self._engines)


engine_registry = EngineRegistry()

###############################################################################
def build_engine_from_connection(connection: dict[str, Any]) -> Engine:
    return engine_registry.get(connection)

###############################################################################
def reset_database_engines() -> None:
    engine_registry.dispose_all()
    with _credential_lock:
        _credential_passwords.clear()

###############################################################################
def validate_connection(connection: dict[str, Any]) -> None:
    try:
        with Session(build_engine_from_connection(connection)) as session:
            session.execute(select(1)).scalar_one()
    except SQLAlchemyError as exc:
        raise ValueError(f"Failed to connect to database: {exc}") from exc

###############################################################################
def inspect_database_schema(
    connection: dict[str, Any], schema: str | None = None
) -> dict[str, Any]:
    engine = build_engine_from_connection(connection)
    namespace = _validate_identifier(schema, "schema") if schema else None
    if engine.dialect.name == "sqlite":
        namespace = None
    try:
        inspector = inspect(engine)
        tables = []
        for table_name in inspector.get_table_names(schema=namespace):
            primary_key = (
                inspector.get_pk_constraint(table_name, schema=namespace) or {}
            )
            foreign_keys = (
                inspector.get_foreign_keys(table_name, schema=namespace) or []
            )
            indexes = inspector.get_indexes(table_name, schema=namespace) or []
            tables.append(
                {
                    "name": table_name,
                    "schema": namespace,
                    "columns": [
                        {
                            "name": str(column.get("name") or ""),
                            "type": str(column.get("type") or ""),
                            "nullable": bool(column.get("nullable", True)),
                            "default": column.get("default"),
                            "primary_key": str(column.get("name") or "")
                            in set(primary_key.get("constrained_columns") or []),
                        }
                        for column in inspector.get_columns(
                            table_name, schema=namespace
                        )
                    ],
                    "primary_key": {
                        "name": primary_key.get("name"),
                        "columns": primary_key.get("constrained_columns") or [],
                    },
                    "foreign_keys": [
                        {
                            "name": fk.get("name"),
                            "columns": fk.get("constrained_columns") or [],
                            "referred_table": fk.get("referred_table"),
                            "referred_columns": fk.get("referred_columns") or [],
                        }
                        for fk in foreign_keys
                    ],
                    "indexes": [
                        {
                            "name": item.get("name"),
                            "columns": item.get("column_names") or [],
                            "unique": bool(item.get("unique", False)),
                        }
                        for item in indexes
                    ],
                }
            )
        return {"schema": namespace, "tables": tables}
    except SQLAlchemyError as exc:
        raise ValueError(f"Failed to inspect database schema: {exc}") from exc

###############################################################################
def _load_table(engine: Engine, table_name: str, schema: str | None = None) -> Table:
    name = _validate_identifier(table_name, "table")
    namespace = _validate_identifier(schema, "schema") if schema else None
    if engine.dialect.name == "sqlite":
        namespace = None
    try:
        return Table(name, MetaData(), schema=namespace, autoload_with=engine)
    except SQLAlchemyError as exc:
        raise ValueError(f"Failed to load table '{name}': {exc}") from exc

###############################################################################
def _validate_columns(table: Table, names: list[str] | set[str], label: str) -> None:
    missing = sorted(name for name in names if name not in table.c)
    if missing:
        raise ValueError(f"Unknown {label} column(s): {', '.join(missing)}")

###############################################################################
def _apply_filters(statement: Any, table: Table, filters: dict[str, Any]) -> Any:
    _validate_columns(table, set(filters), "filter")
    for name, value in filters.items():
        statement = statement.where(table.c[name] == value)
    return statement

###############################################################################
def _require_writable(connection: dict[str, Any], operation: str) -> None:
    if DatabaseConnectionHandle.model_validate(connection).read_only:
        raise ValueError(f"READ_ONLY_VIOLATION: {operation} is not allowed")

###############################################################################
def _result(
    operation: str,
    *,
    rows: list[dict[str, Any]] | None = None,
    affected_rows: int = 0,
    generated_identifiers: list[Any] | None = None,
    limit: int | None = None,
    offset: int = 0,
    total_count: int | None = None,
) -> dict[str, Any]:
    values = rows or []
    return {
        "operation": operation,
        "columns": list(values[0]) if values else [],
        "rows": values,
        "row_count": len(values),
        "affected_rows": affected_rows,
        "generated_identifiers": generated_identifiers or [],
        "pagination": None
        if limit is None
        else {
            "limit": limit,
            "offset": offset,
            "total_count": total_count,
            "has_more": total_count is not None and offset + len(values) < total_count,
        },
        "error": None,
    }

###############################################################################
def execute_create(
    connection: dict[str, Any],
    *,
    table_name: str,
    values: dict[str, Any],
    schema: str | None = None,
) -> dict[str, Any]:
    _require_writable(connection, "create")
    if not values:
        raise ValueError("values must include at least one column")
    engine = build_engine_from_connection(connection)
    try:
        table = _load_table(engine, table_name, schema)
        _validate_columns(table, set(values), "value")
        with engine.begin() as conn:
            result = conn.execute(insert(table).values(**values))
        identifiers = (
            list(result.inserted_primary_key) if result.inserted_primary_key else []
        )
        return _result(
            "create",
            affected_rows=int(result.rowcount or 0),
            generated_identifiers=identifiers,
        )
    except SQLAlchemyError as exc:
        raise ValueError(f"Create operation failed: {exc}") from exc

###############################################################################
def execute_bulk_create(
    connection: dict[str, Any],
    *,
    table_name: str,
    values: list[dict[str, Any]],
    schema: str | None = None,
) -> dict[str, Any]:
    _require_writable(connection, "bulk_create")
    if not values or len(values) > _MAX_BULK_ROWS:
        raise ValueError(f"bulk values must contain 1 to {_MAX_BULK_ROWS} rows")
    engine = build_engine_from_connection(connection)
    try:
        table = _load_table(engine, table_name, schema)
        for item in values:
            _validate_columns(table, set(item), "value")
        with engine.begin() as conn:
            result = conn.execute(insert(table), values)
        return _result("bulk_create", affected_rows=int(result.rowcount or 0))
    except SQLAlchemyError as exc:
        raise ValueError(f"Bulk create operation failed: {exc}") from exc

###############################################################################
def execute_bulk_update(
    connection: dict[str, Any],
    *,
    table_name: str,
    operations: list[dict[str, dict[str, Any]]],
    schema: str | None = None,
) -> dict[str, Any]:
    _require_writable(connection, "bulk_update")
    if not operations or len(operations) > _MAX_BULK_ROWS:
        raise ValueError(f"bulk operations must contain 1 to {_MAX_BULK_ROWS} rows")
    engine = build_engine_from_connection(connection)
    affected = 0
    try:
        table = _load_table(engine, table_name, schema)
        with engine.begin() as conn:
            for operation in operations:
                values = operation.get("values") or {}
                filters = operation.get("filters") or {}
                if not values or not filters:
                    raise ValueError("Each bulk update requires values and filters")
                _validate_columns(table, set(values), "value")
                result = conn.execute(
                    _apply_filters(update(table).values(**values), table, filters)
                )
                affected += int(result.rowcount or 0)
        return _result("bulk_update", affected_rows=affected)
    except SQLAlchemyError as exc:
        raise ValueError(f"Bulk update operation failed: {exc}") from exc

###############################################################################
def execute_bulk_delete(
    connection: dict[str, Any],
    *,
    table_name: str,
    filters: list[dict[str, Any]],
    schema: str | None = None,
) -> dict[str, Any]:
    _require_writable(connection, "bulk_delete")
    if (
        not filters
        or len(filters) > _MAX_BULK_ROWS
        or any(not item for item in filters)
    ):
        raise ValueError(
            f"bulk filters must contain 1 to {_MAX_BULK_ROWS} non-empty rows"
        )
    engine = build_engine_from_connection(connection)
    affected = 0
    try:
        table = _load_table(engine, table_name, schema)
        with engine.begin() as conn:
            for item in filters:
                result = conn.execute(_apply_filters(delete(table), table, item))
                affected += int(result.rowcount or 0)
        return _result("bulk_delete", affected_rows=affected)
    except SQLAlchemyError as exc:
        raise ValueError(f"Bulk delete operation failed: {exc}") from exc

###############################################################################
def execute_read(
    connection: dict[str, Any],
    *,
    table_name: str,
    columns: list[str],
    filters: dict[str, Any],
    limit: int,
    order_by: str,
    offset: int = 0,
    schema: str | None = None,
) -> dict[str, Any]:
    if limit < 1 or limit > _MAX_PAGE_SIZE or offset < 0:
        raise ValueError(
            f"limit must be 1..{_MAX_PAGE_SIZE} and offset must be non-negative"
        )
    engine = build_engine_from_connection(connection)
    try:
        table = _load_table(engine, table_name, schema)
        selected = columns or [column.name for column in table.columns]
        _validate_columns(table, selected, "selected")
        order = order_by.strip()
        if not order:
            primary = [column.name for column in table.primary_key.columns]
            order = primary[0] if primary else selected[0]
        _validate_columns(table, [order], "order_by")
        statement = _apply_filters(
            select(*(table.c[name] for name in selected)), table, filters
        )
        count_statement = _apply_filters(
            select(func.count()).select_from(table), table, filters
        )
        with Session(engine) as session:
            total = int(session.execute(count_statement).scalar_one())
            rows = [
                dict(row)
                for row in session.execute(
                    statement.order_by(table.c[order]).limit(limit).offset(offset)
                ).mappings()
            ]
        return _result("read", rows=rows, limit=limit, offset=offset, total_count=total)
    except SQLAlchemyError as exc:
        raise ValueError(f"Read operation failed: {exc}") from exc

###############################################################################
def execute_update(
    connection: dict[str, Any],
    *,
    table_name: str,
    values: dict[str, Any],
    filters: dict[str, Any],
    schema: str | None = None,
    version_column: str | None = None,
    expected_version: Any = None,
    increment_version: bool = False,
) -> dict[str, Any]:
    _require_writable(connection, "update")
    if not values or not filters:
        raise ValueError("values and filters are required for update operations")
    engine = build_engine_from_connection(connection)
    try:
        table = _load_table(engine, table_name, schema)
        payload = dict(values)
        statement = _apply_filters(update(table), table, filters)
        if version_column:
            _validate_columns(table, [version_column], "version")
            statement = statement.where(table.c[version_column] == expected_version)
            if increment_version:
                payload[version_column] = table.c[version_column] + 1
        _validate_columns(table, set(payload), "value")
        with engine.begin() as conn:
            result = conn.execute(statement.values(**payload))
        return _result("update", affected_rows=int(result.rowcount or 0))
    except SQLAlchemyError as exc:
        raise ValueError(f"Update operation failed: {exc}") from exc

###############################################################################
def execute_delete(
    connection: dict[str, Any],
    *,
    table_name: str,
    filters: dict[str, Any],
    schema: str | None = None,
    version_column: str | None = None,
    expected_version: Any = None,
) -> dict[str, Any]:
    _require_writable(connection, "delete")
    if not filters:
        raise ValueError("filters are required for delete operations")
    engine = build_engine_from_connection(connection)
    try:
        table = _load_table(engine, table_name, schema)
        statement = _apply_filters(delete(table), table, filters)
        if version_column:
            _validate_columns(table, [version_column], "version")
            statement = statement.where(table.c[version_column] == expected_version)
        with engine.begin() as conn:
            result = conn.execute(statement)
        return _result("delete", affected_rows=int(result.rowcount or 0))
    except SQLAlchemyError as exc:
        raise ValueError(f"Delete operation failed: {exc}") from exc

###############################################################################
def execute_upsert(
    connection: dict[str, Any],
    *,
    table_name: str,
    conflict_columns: list[str],
    insert_values: dict[str, Any],
    update_values: dict[str, Any],
    schema: str | None = None,
) -> dict[str, Any]:
    _require_writable(connection, "upsert")
    engine = build_engine_from_connection(connection)
    dialect_name = engine.dialect.name
    if dialect_name not in {"sqlite", "postgresql"}:
        raise ValueError(f"UPSERT_UNSUPPORTED: {dialect_name}")
    table = _load_table(engine, table_name, schema)
    _validate_columns(
        table, set(conflict_columns) | set(insert_values) | set(update_values), "upsert"
    )
    if dialect_name == "sqlite":
        statement = (
            sqlite_insert(table)
            .values(**insert_values)
            .on_conflict_do_update(index_elements=conflict_columns, set_=update_values)
        )
    else:
        statement = (
            postgresql_insert(table)
            .values(**insert_values)
            .on_conflict_do_update(index_elements=conflict_columns, set_=update_values)
        )
    try:
        with engine.begin() as conn:
            result = conn.execute(statement)
        return _result("upsert", affected_rows=int(result.rowcount or 0))
    except SQLAlchemyError as exc:
        raise ValueError(f"Upsert operation failed: {exc}") from exc

###############################################################################
def execute_custom_sql(
    connection: dict[str, Any],
    *,
    sql: str,
    parameters: dict[str, Any] | None = None,
    read_only: bool = True,
) -> dict[str, Any]:
    normalized = sql.strip().rstrip(";")
    without_literals = re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", "", normalized)
    if ";" in without_literals:
        raise ValueError("MULTIPLE_STATEMENTS: custom SQL must contain one statement")
    is_read = bool(_READ_ONLY_SQL.match(normalized))
    if read_only and not is_read:
        raise ValueError("READ_ONLY_SQL_REQUIRED: custom SQL must be a query")
    if not is_read:
        _require_writable(connection, "custom_sql")
    try:
        with build_engine_from_connection(connection).begin() as conn:
            result = conn.execute(text(normalized), parameters or {})
            rows = (
                [dict(row) for row in result.mappings()] if result.returns_rows else []
            )
            return _result(
                "custom_sql",
                rows=rows,
                affected_rows=int(result.rowcount or 0)
                if not result.returns_rows
                else len(rows),
            )
    except SQLAlchemyError as exc:
        raise ValueError(f"Custom SQL operation failed: {exc}") from exc
