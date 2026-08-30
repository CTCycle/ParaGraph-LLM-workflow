from __future__ import annotations

from pathlib import Path

from server.common.utils.logger import logger
from server.configurations.startup import get_server_settings
from server.configurations.settings import SQLiteSettings
from server.repositories.database.migration import run_database_migrations


###############################################################################
def initialize_sqlite_database(
    settings: SQLiteSettings, *, db_path: Path | None = None
) -> None:
    del settings
    run_database_migrations(db_path)
    logger.info("Application database is synchronized")


###############################################################################
def run_database_initialization() -> None:
    settings = get_server_settings().database
    initialize_sqlite_database(settings)


###############################################################################
def initialize_database() -> None:
    run_database_initialization()
