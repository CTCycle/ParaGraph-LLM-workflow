from __future__ import annotations

import urllib.parse

import pandas as pd
import sqlalchemy
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from ParaGraph.server.common.utils.logger import logger
from ParaGraph.server.configurations import DatabaseSettings
from ParaGraph.server.repositories.database.utils import normalize_postgres_engine


###############################################################################
class PostgresRepository:
    def __init__(self, settings: DatabaseSettings) -> None:
        if not settings.host:
            raise ValueError("Database host must be provided for external database.")
        if not settings.database_name:
            raise ValueError("Database name must be provided for external database.")
        if not settings.username:
            raise ValueError("Database username must be provided for external database.")

        port = settings.port or 5432
        engine_name = normalize_postgres_engine(settings.engine)
        password = settings.password or ""
        connect_args: dict[str, str | int] = {"connect_timeout": settings.connect_timeout}
        if settings.ssl:
            connect_args["sslmode"] = "require"
            if settings.ssl_ca:
                connect_args["sslrootcert"] = settings.ssl_ca

        safe_username = urllib.parse.quote_plus(settings.username)
        safe_password = urllib.parse.quote_plus(password)
        self.db_path: str | None = None
        self.engine: Engine = sqlalchemy.create_engine(
            f"{engine_name}://{safe_username}:{safe_password}@{settings.host}:{port}/{settings.database_name}",
            echo=False,
            future=True,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        self.session = sessionmaker(bind=self.engine, future=True)

    # -------------------------------------------------------------------------
    def load_from_database(
        self,
        table_name: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> pd.DataFrame:
        with self.engine.connect() as conn:
            inspector = inspect(conn)
            if not inspector.has_table(table_name):
                logger.warning("Table %s does not exist", table_name)
                return pd.DataFrame()
            data = pd.read_sql_table(table_name, conn)
        if offset:
            data = data.iloc[offset:]
        if limit is not None:
            data = data.head(limit)
        return data.reset_index(drop=True)

    # -------------------------------------------------------------------------
    def save_into_database(self, df: pd.DataFrame, table_name: str) -> None:
        with self.engine.begin() as conn:
            inspector = inspect(conn)
            if inspector.has_table(table_name):
                conn.execute(sqlalchemy.text(f'DELETE FROM "{table_name}"'))
            df.to_sql(table_name, conn, if_exists="append", index=False)

    # -------------------------------------------------------------------------
    def upsert_into_database(self, df: pd.DataFrame, table_name: str) -> None:
        self.save_into_database(df, table_name)

    # -------------------------------------------------------------------------
    def count_rows(self, table_name: str) -> int:
        with self.engine.connect() as conn:
            result = conn.execute(sqlalchemy.text(f'SELECT COUNT(*) FROM "{table_name}"'))
            value = result.scalar() or 0
        return int(value)

