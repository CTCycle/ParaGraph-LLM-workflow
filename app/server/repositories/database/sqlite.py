from __future__ import annotations

import os

import sqlalchemy

from server.common.constants import DATABASE_FILENAME, RESOURCES_PATH
from server.domain.settings import DatabaseSettings
from server.repositories.database.base import TabularDatabaseRepository


###############################################################################
class SQLiteRepository(TabularDatabaseRepository):
    def __init__(self, settings: DatabaseSettings) -> None:
        db_path = os.path.join(RESOURCES_PATH, DATABASE_FILENAME)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        engine = sqlalchemy.create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            future=True,
        )
        super().__init__(
            engine=engine,
            db_path=db_path,
            insert_batch_size=settings.insert_batch_size,
        )

