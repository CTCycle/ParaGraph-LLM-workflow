from __future__ import annotations

from ParaGraph.server.domain.settings import DatabaseSettings
from ParaGraph.server.repositories.database.postgres import PostgresRepository
from ParaGraph.server.repositories.database.sqlite import SQLiteRepository
from ParaGraph.server.repositories.database.utils import normalize_postgres_engine


class DatabaseRepositoryFactory:
    _SUPPORTED_POSTGRES_ENGINES = {
        "postgres",
        "postgresql",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    }

    def build(self, settings: DatabaseSettings) -> SQLiteRepository | PostgresRepository:
        if settings.embedded_database:
            return SQLiteRepository(settings)

        engine_name = normalize_postgres_engine(settings.engine).lower()
        if engine_name not in self._SUPPORTED_POSTGRES_ENGINES:
            raise ValueError(f"Unsupported database engine: {settings.engine}")
        return PostgresRepository(settings)
