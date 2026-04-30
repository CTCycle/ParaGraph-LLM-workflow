from __future__ import annotations

import urllib.parse

import sqlalchemy
from sqlalchemy import MetaData, Table, select
from sqlalchemy.exc import SQLAlchemyError

from server.common.utils.logger import logger
from server.configurations.startup import get_server_settings
from server.domain.settings import DatabaseSettings
from server.repositories.database.factory import DatabaseRepositoryFactory
from server.repositories.database.postgres import PostgresRepository
from server.repositories.database.sqlite import SQLiteRepository
from server.repositories.database.utils import normalize_postgres_engine
from server.repositories.schemas import Base


# -----------------------------------------------------------------------------
def build_postgres_connect_args(settings: DatabaseSettings) -> dict[str, str | int]:
    connect_args: dict[str, str | int] = {
        "connect_timeout": settings.connect_timeout,
        "client_encoding": "utf8",
    }
    if settings.ssl:
        connect_args["sslmode"] = "require"
        if settings.ssl_ca:
            connect_args["sslrootcert"] = settings.ssl_ca
    return connect_args


# -----------------------------------------------------------------------------
def build_postgres_url(settings: DatabaseSettings, database_name: str) -> str:
    port = settings.port or 5432
    engine_name = normalize_postgres_engine(settings.engine)
    safe_username = urllib.parse.quote_plus(settings.username or "")
    safe_password = urllib.parse.quote_plus(settings.password or "")
    return f"{engine_name}://{safe_username}:{safe_password}@{settings.host}:{port}/{database_name}"


# -----------------------------------------------------------------------------
def initialize_sqlite_database(settings: DatabaseSettings) -> None:
    repository = SQLiteRepository(settings)
    Base.metadata.create_all(repository.engine)
    logger.info("Initialized SQLite database at %s", repository.db_path)


# -----------------------------------------------------------------------------
def ensure_postgres_database(settings: DatabaseSettings) -> str:
    if not settings.host:
        raise ValueError("Database host is required for PostgreSQL initialization.")
    if not settings.username:
        raise ValueError("Database username is required for PostgreSQL initialization.")
    if not settings.database_name:
        raise ValueError("Database name is required for PostgreSQL initialization.")

    target_database = settings.database_name
    connect_args = build_postgres_connect_args(settings)
    admin_url = build_postgres_url(settings, "postgres")
    admin_engine = sqlalchemy.create_engine(
        admin_url,
        echo=False,
        future=True,
        connect_args=connect_args,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )

    with admin_engine.connect() as conn:
        catalog = Table(
            "pg_database", MetaData(), schema="pg_catalog", autoload_with=admin_engine
        )
        exists = conn.execute(
            select(catalog.c.datname)
            .where(catalog.c.datname == target_database)
            .limit(1)
        ).scalar_one_or_none()
        if not exists:
            safe_database = target_database.replace('"', '""')
            # CREATE DATABASE is a PostgreSQL DDL command that is not representable through SQLAlchemy ORM constructs.
            conn.exec_driver_sql(
                f"CREATE DATABASE \"{safe_database}\" WITH ENCODING 'UTF8' TEMPLATE template0"
            )
            logger.info("Created PostgreSQL database %s", target_database)

    repository = PostgresRepository(settings)
    Base.metadata.create_all(repository.engine)
    logger.info("Ensured PostgreSQL tables exist in %s", target_database)
    return target_database


# -----------------------------------------------------------------------------
def run_database_initialization() -> None:
    settings = get_server_settings().database
    repository = DatabaseRepositoryFactory().build(settings)
    if isinstance(repository, SQLiteRepository):
        initialize_sqlite_database(settings)
        return

    ensure_postgres_database(settings)


# -----------------------------------------------------------------------------
def initialize_database() -> None:
    try:
        run_database_initialization()
    except (SQLAlchemyError, ValueError) as exc:
        logger.error("Database initialization failed: %s", exc)
        raise SystemExit(1) from exc
    except Exception as exc:
        logger.exception("Unexpected error during database initialization.")
        raise SystemExit(1) from exc

