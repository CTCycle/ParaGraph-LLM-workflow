from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import portalocker
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine, URL, create_engine
from sqlalchemy.pool import NullPool

from server.common import path as common_path
from server.common.constants import DATABASE_FILENAME
from server.common.utils.logger import logger
from server.repositories.database.sqlite_policy import configure_sqlite_engine
from server.repositories.schemas import Base


MIGRATION_VERSION_TABLE = "alembic_version"
MIGRATION_LOCK_TIMEOUT_SECONDS = 120.0
SQLITE_TIMEOUT_SECONDS = 30.0
_APPLICATION_TABLE_NAMES = frozenset(Base.metadata.tables)


###############################################################################
class DatabaseMigrationError(RuntimeError):
    """Raised when the internal application schema cannot be synchronized."""


###############################################################################
def default_database_path() -> Path:
    return common_path.RESOURCES_ROOT / DATABASE_FILENAME


###############################################################################
def _sqlite_url(database_path: Path) -> URL:
    return URL.create("sqlite", database=str(database_path))


###############################################################################
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


###############################################################################
def _alembic_config(database_path: Path) -> Config:
    config = Config(toml_file=str(common_path.SERVER_ROOT / "pyproject.toml"))
    config.set_main_option(
        "sqlalchemy.url",
        _sqlite_url(database_path)
        .render_as_string(hide_password=False)
        .replace("%", "%%"),
    )
    config.attributes["database_path"] = str(database_path)
    return config


###############################################################################
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


###############################################################################
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


###############################################################################
def _current_revisions(connection: Connection) -> tuple[str, ...]:
    version_table_exists = inspect(connection).has_table(MIGRATION_VERSION_TABLE)
    if not version_table_exists:
        return ()
    from alembic.runtime.migration import MigrationContext

    return tuple(MigrationContext.configure(connection).get_current_heads())


###############################################################################
def _application_tables(connection: Connection) -> set[str]:
    return set(inspect(connection).get_table_names()).intersection(
        _APPLICATION_TABLE_NAMES
    )


###############################################################################
def _require_complete_application_schema(connection: Connection) -> None:
    application_tables = _application_tables(connection)
    if application_tables == _APPLICATION_TABLE_NAMES:
        return
    missing = sorted(_APPLICATION_TABLE_NAMES - application_tables)
    raise DatabaseMigrationError(
        "Versioned application schema is incomplete; missing tables: "
        + ", ".join(missing)
    )


###############################################################################
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


###############################################################################
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


###############################################################################
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
            table_names = set(inspect(connection).get_table_names())
            table_names.discard(MIGRATION_VERSION_TABLE)
            if not current_revisions and table_names:
                raise DatabaseMigrationError(
                    "Database has application tables but no Alembic revision; "
                    "refusing to adopt an unsupported unversioned schema."
                )
            if not current_revisions:
                logger.info(
                    "Creating a new application database at Alembic head %s", head
                )
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


###############################################################################
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
