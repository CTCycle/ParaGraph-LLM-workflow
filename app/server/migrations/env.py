from __future__ import annotations

from typing import Any

from alembic import context
from alembic.util.exc import CommandError
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from server.configurations.settings import get_sqlite_settings_from_env
from server.repositories.database.sqlite_policy import configure_sqlite_engine
from server.repositories.database.sqlite import SQLiteRepository
from server.repositories.schemas import Base


config = context.config
target_metadata = Base.metadata
_VERSION_TABLE = "alembic_version"


###############################################################################
def _include_object(
    object_: Any,
    name: str | None,
    object_type: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """Keep Alembic focused on application-owned ORM tables.

    The SQLiteRepository deliberately supports explicit dynamic tables for
    user data. Those tables must not be interpreted as removed application
    tables during autogeneration or ``alembic check``.
    """

    if object_type == "table":
        return name != _VERSION_TABLE and name in target_metadata.tables

    table = getattr(object_, "table", None)
    table_name = getattr(table, "name", None)
    if table_name is None and compare_to is not None:
        table_name = getattr(getattr(compare_to, "table", None), "name", None)
    if table_name is None:
        return True
    return table_name in target_metadata.tables


###############################################################################
def _database_url() -> str:
    try:
        configured_url = config.get_main_option("sqlalchemy.url")
    except CommandError:
        configured_url = None
    if configured_url:
        return configured_url

    repository = SQLiteRepository(get_sqlite_settings_from_env())
    try:
        return repository.engine.url.render_as_string(hide_password=False)
    finally:
        repository.engine.dispose()


###############################################################################
def _migration_options(connection: Connection) -> dict[str, Any]:
    return {
        "connection": connection,
        "target_metadata": target_metadata,
        "include_object": _include_object,
        "render_as_batch": True,
        "compare_type": True,
        "compare_server_default": False,
        "transactional_ddl": True,
        "version_table": _VERSION_TABLE,
    }


###############################################################################
def _run_migrations(connection: Connection) -> None:
    context.configure(**_migration_options(connection))
    with context.begin_transaction():
        context.run_migrations()


###############################################################################
def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        include_object=_include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
        compare_server_default=False,
        transactional_ddl=True,
        version_table=_VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


###############################################################################
def run_migrations_online() -> None:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        _run_migrations(supplied_connection)
        return

    database_url = _database_url()
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args = {"autocommit": False, "timeout": 30.0}
    engine = configure_sqlite_engine(
        create_engine(
            database_url,
            future=True,
            poolclass=pool.NullPool,
            connect_args=connect_args,
        )
    )
    try:
        with engine.connect() as connection:
            _run_migrations(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
