from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.configurations.startup import get_server_settings
from server.repositories.database.initializer import initialize_database
from server.repositories.database.migration import DatabaseMigrationError
from server.common.utils.logger import logger


###############################################################################
if __name__ == "__main__":
    server_settings = get_server_settings()
    start = time.perf_counter()
    logger.info("Starting database initialization")
    logger.info(
        "Current SQLite configuration: %s",
        json.dumps(asdict(server_settings.database), ensure_ascii=False),
    )
    try:
        initialize_database()
    except DatabaseMigrationError as exc:
        logger.error("Database initialization failed: %s", exc)
        raise SystemExit(1) from exc
    elapsed = time.perf_counter() - start
    logger.info("Database initialization completed in %.2f seconds", elapsed)
