from __future__ import annotations

import urllib.parse

import sqlalchemy

from server.domain.settings import DatabaseSettings
from server.repositories.database.base import TabularDatabaseRepository
from server.repositories.database.utils import normalize_postgres_engine

###############################################################################
class PostgresRepository(TabularDatabaseRepository):

    # -------------------------------------------------------------------------
    def __init__(self, settings: DatabaseSettings) -> None:
        if not settings.host:
            raise ValueError("Database host must be provided for external database.")
        if not settings.database_name:
            raise ValueError("Database name must be provided for external database.")
        if not settings.username:
            raise ValueError(
                "Database username must be provided for external database."
            )

        port = settings.port or 5432
        engine_name = normalize_postgres_engine(settings.engine)
        password = settings.password or ""
        connect_args: dict[str, str | int] = {
            "connect_timeout": settings.connect_timeout
        }
        if settings.ssl:
            connect_args["sslmode"] = "require"
            if settings.ssl_ca:
                connect_args["sslrootcert"] = settings.ssl_ca

        safe_username = urllib.parse.quote_plus(settings.username)
        safe_password = urllib.parse.quote_plus(password)
        engine = sqlalchemy.create_engine(
            f"{engine_name}://{safe_username}:{safe_password}@{settings.host}:{port}/{settings.database_name}",
            echo=False,
            future=True,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        super().__init__(
            engine=engine,
            db_path=None,
            insert_batch_size=settings.insert_batch_size,
        )
