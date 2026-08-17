from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from server.common.utils.logger import logger
from server.configurations.startup import get_server_settings
from server.domain.settings import SQLiteSettings
from server.repositories.database.sqlite import SQLiteRepository
from server.repositories.schemas import Base

###############################################################################
def initialize_sqlite_database(settings: SQLiteSettings) -> None:
    repository = SQLiteRepository(settings)
    Base.metadata.create_all(repository.engine)
    logger.info("Initialized SQLite database at %s", repository.db_path)

###############################################################################
def run_database_initialization() -> None:
    settings = get_server_settings().database
    initialize_sqlite_database(settings)

###############################################################################
def initialize_database() -> None:
    try:
        run_database_initialization()
    except (SQLAlchemyError, ValueError) as exc:
        logger.error("Database initialization failed: %s", exc)
        raise SystemExit(1) from exc
    except Exception as exc:
        logger.exception("Unexpected error during database initialization.")
        raise SystemExit(1) from exc
