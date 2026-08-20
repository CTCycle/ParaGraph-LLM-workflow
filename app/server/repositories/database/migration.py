from __future__ import annotations

from collections.abc import Collection, Iterator
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from typing import Any

import portalocker
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine, URL, create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.sql.schema import MetaData
from sqlalchemy.dialects.sqlite import dialect as sqlite_dialect

from server.common import path as common_path
from server.common.constants import DATABASE_FILENAME
from server.common.utils.logger import logger
from server.repositories.database.sqlite_policy import configure_sqlite_engine
from server.repositories.schemas import Base


BASELINE_REVISION = "0001_initial"
MIGRATION_VERSION_TABLE = "alembic_version"
MIGRATION_LOCK_TIMEOUT_SECONDS = 120.0
SQLITE_TIMEOUT_SECONDS = 30.0
# Frozen normalized signature of the pre-Alembic application schema.
_BASELINE_SCHEMA_FINGERPRINT = "06a4979ba57eb0a4039c77ddc36442f0770427220f4ea83a7119ace43b044557"
_APPLICATION_TABLE_NAMES = frozenset(Base.metadata.tables)
_LEGACY_APPLICATION_TABLE_NAMES = _APPLICATION_TABLE_NAMES | {"nodes"}


class DatabaseMigrationError(RuntimeError):
    """Raised when the internal application schema cannot be synchronized."""


def default_database_path() -> Path:
    return common_path.RESOURCES_ROOT / DATABASE_FILENAME


def _normalize_type(type_: Any) -> str:
    return str(type_.compile(dialect=sqlite_dialect())).upper()


def _metadata_signature(metadata: MetaData) -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    for table in sorted(metadata.tables.values(), key=lambda item: item.name):
        columns = [
            {
                "name": column.name,
                "type": _normalize_type(column.type),
                "nullable": bool(column.nullable),
                "primary_key": bool(column.primary_key),
            }
            for column in table.columns
        ]
        indexes = sorted(
            (
                {
                    "name": index.name,
                    "columns": [column.name for column in index.columns],
                    "unique": bool(index.unique),
                }
                for index in table.indexes
            ),
            key=lambda item: (item["name"] or "", item["columns"]),
        )
        unique_constraints = sorted(
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        )
        foreign_keys = sorted(
            (
                tuple(constraint.column_keys),
                tuple(
                    (
                        foreign_key.target_fullname.split(".")[-2],
                        foreign_key.target_fullname.split(".")[-1],
                        foreign_key.ondelete,
                    )
                    for foreign_key in constraint.elements
                ),
            )
            for constraint in table.foreign_key_constraints
        )
        tables.append(
            {
                "name": table.name,
                "columns": columns,
                "indexes": indexes,
                "unique_constraints": unique_constraints,
                "foreign_keys": foreign_keys,
            }
        )
    return {"tables": tables}


def _inspected_signature(
    connection: Connection,
    table_names: Collection[str] = _APPLICATION_TABLE_NAMES,
) -> dict[str, Any]:
    inspector = inspect(connection)
    tables: list[dict[str, Any]] = []
    for table_name in sorted(table_names):
        columns = inspector.get_columns(table_name)
        indexes = sorted(
            (
                {
                    "name": index.get("name"),
                    "columns": list(index.get("column_names") or []),
                    "unique": bool(index.get("unique")),
                }
                for index in inspector.get_indexes(table_name)
            ),
            key=lambda item: (item["name"] or "", item["columns"]),
        )
        unique_constraints = sorted(
            tuple(constraint.get("column_names") or [])
            for constraint in inspector.get_unique_constraints(table_name)
        )
        foreign_keys = sorted(
            (
                tuple(foreign_key.get("constrained_columns") or []),
                tuple(
                    (
                        foreign_key.get("referred_table"),
                        referred_column,
                        (foreign_key.get("options") or {}).get("ondelete"),
                    )
                    for referred_column in foreign_key.get("referred_columns") or []
                ),
            )
            for foreign_key in inspector.get_foreign_keys(table_name)
        )
        tables.append(
            {
                "name": table_name,
                "columns": [
                    {
                        "name": column["name"],
                        "type": _normalize_type(column["type"]),
                        "nullable": bool(column["nullable"]),
                        "primary_key": bool(column.get("primary_key")),
                    }
                    for column in columns
                ],
                "indexes": indexes,
                "unique_constraints": unique_constraints,
                "foreign_keys": foreign_keys,
            }
        )
    return {"tables": tables}


def _fingerprint(signature: dict[str, Any]) -> str:
    payload = json.dumps(signature, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def metadata_schema_fingerprint() -> str:
    return _fingerprint(_metadata_signature(Base.metadata))


def _database_schema_fingerprint(
    connection: Connection,
    table_names: Collection[str] = _APPLICATION_TABLE_NAMES,
) -> str:
    return _fingerprint(_inspected_signature(connection, table_names))


def _sqlite_url(database_path: Path) -> URL:
    return URL.create("sqlite", database=str(database_path))


def _migration_engine(database_path: Path) -> Engine:
    return configure_sqlite_engine(
        create_engine(
            _sqlite_url(database_path),
            future=True,
            poolclass=NullPool,
            connect_args={
                "autocommit": False,
                "timeout": SQLITE_TIMEOUT_SECONDS,
            },
        )
    )


def _alembic_config(database_path: Path) -> Config:
    config = Config(toml_file=str(common_path.SERVER_ROOT / "pyproject.toml"))
    config.set_main_option(
        "sqlalchemy.url",
        _sqlite_url(database_path).render_as_string(hide_password=False).replace(
            "%", "%%"
        ),
    )
    config.attributes["database_path"] = str(database_path)
    return config


@contextmanager
def _migration_lock(database_path: Path) -> Iterator[None]:
    lock_path = database_path.with_name(f"{database_path.name}.migration.lock")
    try:
        with portalocker.Lock(
            str(lock_path),
            mode="a",
            timeout=MIGRATION_LOCK_TIMEOUT_SECONDS,
        ):
            yield
    except portalocker.exceptions.LockException as exc:
        raise DatabaseMigrationError(
            "Timed out waiting for database migration lock after "
            f"{MIGRATION_LOCK_TIMEOUT_SECONDS:.0f}s: {lock_path}"
        ) from exc


def _script_directory(config: Config) -> tuple[ScriptDirectory, str]:
    try:
        script = ScriptDirectory.from_config(config)
        heads = script.get_heads()
    except (CommandError, RuntimeError) as exc:
        raise DatabaseMigrationError("Alembic migration discovery failed") from exc
    if len(heads) != 1:
        raise DatabaseMigrationError(
            "Alembic must have exactly one migration head; "
            f"found {len(heads)}: {', '.join(heads) or 'none'}"
        )
    return script, heads[0]


def _current_revisions(connection: Connection) -> tuple[str, ...]:
    version_table_exists = inspect(connection).has_table(MIGRATION_VERSION_TABLE)
    if not version_table_exists:
        return ()
    from alembic.runtime.migration import MigrationContext

    return tuple(MigrationContext.configure(connection).get_current_heads())


def _application_tables(connection: Connection) -> set[str]:
    return set(inspect(connection).get_table_names()).intersection(
        _APPLICATION_TABLE_NAMES
    )


def _require_complete_application_schema(connection: Connection) -> None:
    application_tables = _application_tables(connection)
    if application_tables == _APPLICATION_TABLE_NAMES:
        return
    missing = sorted(_APPLICATION_TABLE_NAMES - application_tables)
    raise DatabaseMigrationError(
        "Versioned application schema is incomplete; missing tables: "
        + ", ".join(missing)
    )


def _legacy_schema_state(connection: Connection) -> str:
    application_tables = _application_tables(connection)
    legacy_application_tables = set(inspect(connection).get_table_names()).intersection(
        _LEGACY_APPLICATION_TABLE_NAMES
    )
    if legacy_application_tables == _LEGACY_APPLICATION_TABLE_NAMES:
        observed = _database_schema_fingerprint(
            connection, _LEGACY_APPLICATION_TABLE_NAMES
        )
        if observed == _BASELINE_SCHEMA_FINGERPRINT:
            return "baseline"
    if not application_tables:
        return "empty"
    if application_tables != _APPLICATION_TABLE_NAMES:
        missing = sorted(_APPLICATION_TABLE_NAMES - application_tables)
        raise DatabaseMigrationError(
            "Existing application schema is incomplete; missing tables: "
            + ", ".join(missing)
        )

    observed = _database_schema_fingerprint(connection)
    if observed == _BASELINE_SCHEMA_FINGERPRINT:
        return "baseline"
    raise DatabaseMigrationError(
        "Existing application tables do not match the supported pre-Alembic "
        "schema. Database initialization stopped without changing the schema."
    )


def _validate_current_revision(
    script: ScriptDirectory, current: str, head: str
) -> list[str]:
    if current == head:
        return []
    try:
        pending = list(script.iterate_revisions(head, current))
    except Exception as exc:
        raise DatabaseMigrationError(
            f"Database revision {current!r} is not an ancestor of Alembic head {head!r}"
        ) from exc
    if not pending:
        raise DatabaseMigrationError(
            f"Database revision {current!r} cannot be upgraded to Alembic head {head!r}"
        )
    return [revision.revision for revision in reversed(pending)]


def _upgrade_to_head(
    config: Config, connection: Connection, script: ScriptDirectory, head: str
) -> None:
    current_revisions = _current_revisions(connection)
    if len(current_revisions) > 1:
        raise DatabaseMigrationError(
            "Database contains multiple Alembic revisions; resolve the branch "
            "state manually before starting the application."
        )
    current = current_revisions[0] if current_revisions else None
    if current is None:
        logger.info("No Alembic revision detected; upgrading the database to %s", head)
    else:
        pending = _validate_current_revision(script, current, head)
        if not pending:
            logger.info("Database is already synchronized at Alembic head %s", head)
            return
        logger.info(
            "Database is at Alembic revision %s; applying revisions: %s",
            current,
            ", ".join(pending),
        )
    config.attributes["connection"] = connection
    command.upgrade(config, head)


def _synchronize_locked(database_path: Path) -> None:
    engine: Engine | None = None
    try:
        config = _alembic_config(database_path)
        script, head = _script_directory(config)
        logger.info("Application database migration target head: %s", head)
        engine = _migration_engine(database_path)
        with engine.begin() as connection:
            current_revisions = _current_revisions(connection)
            if len(current_revisions) > 1:
                raise DatabaseMigrationError(
                    "Database contains multiple Alembic revisions; resolve the "
                    "branch state manually before starting the application."
                )
            if current_revisions == (head,):
                _require_complete_application_schema(connection)
            has_version_table = inspect(connection).has_table(MIGRATION_VERSION_TABLE)
            if not current_revisions and (not has_version_table or _application_tables(connection)):
                legacy_state = _legacy_schema_state(connection)
                if legacy_state == "baseline":
                    logger.info(
                        "Adopting the legacy application schema at revision %s",
                        BASELINE_REVISION,
                    )
                    config.attributes["connection"] = connection
                    command.stamp(config, BASELINE_REVISION)
                elif legacy_state == "empty":
                    logger.info("Creating a new application database at Alembic head %s", head)
            _upgrade_to_head(config, connection, script, head)
            if _current_revisions(connection) == (head,):
                _require_complete_application_schema(connection)
    except DatabaseMigrationError:
        raise
    except Exception as exc:
        raise DatabaseMigrationError(
            f"Alembic failed while synchronizing {database_path}"
        ) from exc
    finally:
        if engine is not None:
            engine.dispose()


def run_database_migrations(database_path: Path | None = None) -> None:
    resolved_path = (database_path or default_database_path()).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Checking application database schema at %s", resolved_path)
    try:
        with _migration_lock(resolved_path):
            _synchronize_locked(resolved_path)
    except DatabaseMigrationError:
        logger.exception(
            "Application database migration failed at %s; any active migration "
            "transaction was rolled back",
            resolved_path,
        )
        raise
