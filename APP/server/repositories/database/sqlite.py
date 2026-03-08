from __future__ import annotations

import os

import pandas as pd
import sqlalchemy
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from APP.server.common.constants import DATABASE_FILENAME, RESOURCES_PATH
from APP.server.common.utils.logger import logger
from APP.server.configurations import DatabaseSettings


###############################################################################
class SQLiteRepository:
    def __init__(self, settings: DatabaseSettings) -> None:
        self.db_path: str | None = os.path.join(RESOURCES_PATH, "database", DATABASE_FILENAME)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.engine: Engine = sqlalchemy.create_engine(f"sqlite:///{self.db_path}", echo=False, future=True)
        self.session = sessionmaker(bind=self.engine, future=True)
        self.insert_batch_size = settings.insert_batch_size

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
        # Placeholder behavior for template: replace-based upsert.
        self.save_into_database(df, table_name)

    # -------------------------------------------------------------------------
    def count_rows(self, table_name: str) -> int:
        with self.engine.connect() as conn:
            result = conn.execute(sqlalchemy.text(f'SELECT COUNT(*) FROM "{table_name}"'))
            value = result.scalar() or 0
        return int(value)
