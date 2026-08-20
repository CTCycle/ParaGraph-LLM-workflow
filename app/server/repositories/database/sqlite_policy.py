from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine


_CONFIGURED_ATTRIBUTE = "_paragraph_sqlite_foreign_keys_configured"


def _enable_foreign_keys(dbapi_connection: Any) -> None:
    autocommit = getattr(dbapi_connection, "autocommit", None)
    if autocommit is not None:
        dbapi_connection.autocommit = True
    try:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()
    finally:
        if autocommit is not None:
            dbapi_connection.autocommit = autocommit


def _enable_foreign_keys_on_checkout(
    dbapi_connection: Any,
    _connection_record: Any,
    _connection_proxy: Any,
) -> None:
    _enable_foreign_keys(dbapi_connection)


def configure_sqlite_engine(engine: Engine) -> Engine:
    """Apply the application SQLite connection policy to an engine."""

    if engine.dialect.name != "sqlite":
        return engine
    if getattr(engine, _CONFIGURED_ATTRIBUTE, False):
        return engine

    event.listen(engine, "checkout", _enable_foreign_keys_on_checkout)
    setattr(engine, _CONFIGURED_ATTRIBUTE, True)
    return engine
