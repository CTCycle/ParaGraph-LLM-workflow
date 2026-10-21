from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from dotenv import dotenv_values

from server.common import path as common_path
from server.configurations.environment import EnvironmentLoader
from server.configurations.settings import (
    GlobalSettings,
    JobsSettings,
    SQLiteSettings,
    ServerSettings,
)
from server.repositories.database.configuration import (
    DatabaseConfiguration,
    DatabaseConfigurationError,
    configuration_path,
    load_database_configuration,
    save_database_configuration,
)
from server.repositories.database.migration import run_database_migrations
from server.repositories.database.sqlite_policy import configure_sqlite_engine
from server.repositories.schemas import ApplicationSettingsRecord


###############################################################################
class DatabaseUnavailableError(RuntimeError):
    pass


###############################################################################
class DatabaseBusyError(RuntimeError):
    pass


###############################################################################
class DatabaseRuntime:
    """Owns the active engine and fences repository work during a switch."""

    # -------------------------------------------------------------------------
    def __init__(
        self, *, persist_configuration: bool = True, publish_settings: bool = True
    ) -> None:
        self._condition = threading.Condition(threading.RLock())
        self._engine: Engine | None = None
        self._configuration: DatabaseConfiguration | None = None
        self._configuration_file: Path | None = None
        self._error: str | None = None
        self._switching = False
        self._active_operations = 0
        self._persist_configuration = persist_configuration
        self._publish_settings = publish_settings
        self._settings = ServerSettings(
            database=SQLiteSettings(insert_batch_size=1000),
            global_settings=GlobalSettings(seed=42),
            jobs=JobsSettings(polling_interval=1.0, retention_days=30),
        )

    # -------------------------------------------------------------------------
    @property
    def settings(self) -> ServerSettings:
        with self._condition:
            return self._settings

    # -------------------------------------------------------------------------
    @contextmanager
    def operation(self) -> Iterator[None]:
        """Fence a complete multi-step operation against database switching."""
        with self._condition:
            while self._switching:
                self._condition.wait()
            if self._engine is None:
                raise DatabaseUnavailableError(self._error or "Application database is unavailable")
            self._active_operations += 1
        try:
            yield
        finally:
            with self._condition:
                self._active_operations -= 1
                self._condition.notify_all()

    # -------------------------------------------------------------------------
    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._condition:
            while self._switching:
                self._condition.wait()
            if self._engine is None:
                raise DatabaseUnavailableError(self._error or "Application database is unavailable")
            engine = self._engine
            self._active_operations += 1
        try:
            with Session(engine) as session:
                yield session
        finally:
            with self._condition:
                self._active_operations -= 1
                self._condition.notify_all()

    # -------------------------------------------------------------------------
    def status(self) -> dict[str, object]:
        with self._condition:
            return {
                "configuration": self._configuration.model_dump() if self._configuration else None,
                "database_path": str(self._configuration.resolved_path()) if self._configuration else None,
                "connected": self._engine is not None,
                "error": self._error,
            }

    # -------------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        with self._condition:
            previous = self._engine
            self._engine = None
            self._configuration = None
            self._configuration_file = None
            self._error = None
            self._active_operations = 0
            self._switching = False
            self._condition.notify_all()
        if previous is not None:
            previous.dispose()

    # -------------------------------------------------------------------------
    def initialize(self) -> None:
        config_file = configuration_path()
        if self._engine is not None and self._configuration_file == config_file.resolve():
            try:
                if load_database_configuration() == self._configuration:
                    EnvironmentLoader().ensure_loaded()
                    return
            except DatabaseConfigurationError:
                pass
        configuration: DatabaseConfiguration | None = None
        try:
            if not config_file.exists():
                legacy_values = dotenv_values(common_path.ENV_FILE) if common_path.ENV_FILE.is_file() else {}
                legacy_batch_size = legacy_values.get("DATABASE_INSERT_BATCH_SIZE") or "1000"
                try:
                    initial = DatabaseConfiguration(insert_batch_size=int(legacy_batch_size))
                except (ValueError, TypeError) as exc:
                    raise DatabaseConfigurationError("Legacy DATABASE_INSERT_BATCH_SIZE must be an integer") from exc
                save_database_configuration(initial)
            self._remove_legacy_batch_setting()
            EnvironmentLoader().ensure_loaded()
            configuration = load_database_configuration()
            self._activate(configuration, import_legacy_settings=True, persist=False)
        except Exception as exc:
            with self._condition:
                if self._engine is None:
                    self._configuration = configuration
                    self._configuration_file = config_file.resolve()
                self._error = str(exc)
            raise

    # -------------------------------------------------------------------------
    def test(self, configuration: DatabaseConfiguration) -> None:
        target = configuration.resolved_path()
        if target.exists():
            try:
                connection = sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True, timeout=3)
                try:
                    result = connection.execute("PRAGMA quick_check").fetchone()
                    if not result or result[0] != "ok":
                        raise DatabaseConfigurationError("SQLite integrity check failed")
                    version = connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
                    ).fetchone()
                    if version:
                        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
                        from alembic.config import Config
                        from alembic.script import ScriptDirectory

                        script_config = Config(toml_file=str(common_path.SERVER_ROOT / "pyproject.toml"))
                        script = ScriptDirectory.from_config(script_config)
                        if revision is None or script.get_revision(str(revision[0])) is None:
                            raise DatabaseConfigurationError("Database schema revision is unknown")
                    else:
                        user_tables = connection.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                        ).fetchall()
                        if user_tables:
                            raise DatabaseConfigurationError("Database contains an unversioned schema")
                finally:
                    connection.close()
            except (sqlite3.Error, OSError) as exc:
                raise DatabaseConfigurationError(f"SQLite connection failed: {exc}") from exc
            return

        if not target.parent.is_dir():
            raise DatabaseConfigurationError(f"Database directory does not exist: {target.parent}")
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".database-test-", delete=True):
                pass
        except OSError as exc:
            raise DatabaseConfigurationError(f"Database directory is not writable: {exc}") from exc

    # -------------------------------------------------------------------------
    def activate(self, configuration: DatabaseConfiguration) -> None:
        from server.services.jobs import job_manager

        with self._condition:
            if self._switching:
                raise DatabaseBusyError("A database change is already in progress")
            if job_manager.is_job_running(job_type="workflow"):
                raise DatabaseBusyError("Finish or cancel the active workflow before switching databases")
            self._switching = True
            while self._active_operations:
                self._condition.wait(timeout=0.1)
            if job_manager.is_job_running(job_type="workflow"):
                self._switching = False
                self._condition.notify_all()
                raise DatabaseBusyError("Finish or cancel the active workflow before switching databases")

        try:
            self._activate(configuration, import_legacy_settings=False, persist=True)
        finally:
            with self._condition:
                self._switching = False
                self._condition.notify_all()

    # -------------------------------------------------------------------------
    def _activate(
        self,
        configuration: DatabaseConfiguration,
        *,
        import_legacy_settings: bool,
        persist: bool,
    ) -> None:
        target = configuration.resolved_path()
        run_database_migrations(target)
        candidate = configure_sqlite_engine(
            create_engine(f"sqlite:///{target.as_posix()}", future=True, connect_args={"timeout": 30.0})
        )
        try:
            settings = self._load_settings(candidate, import_legacy=import_legacy_settings)
            if persist and self._persist_configuration:
                save_database_configuration(configuration)
        except Exception:
            candidate.dispose()
            raise

        with self._condition:
            previous = self._engine
            self._engine = candidate
            self._configuration = configuration
            self._configuration_file = configuration_path().resolve()
            self._settings = ServerSettings(
                database=SQLiteSettings(insert_batch_size=configuration.insert_batch_size),
                global_settings=GlobalSettings(seed=settings[0]),
                jobs=JobsSettings(polling_interval=settings[1], retention_days=settings[2]),
            )
            self._error = None
        if previous is not None:
            previous.dispose()
        if self._publish_settings:
            from server.configurations.startup import install_server_settings

            install_server_settings(self.settings)

    # -------------------------------------------------------------------------
    def _load_settings(
        self, engine: Engine, *, import_legacy: bool
    ) -> tuple[int, float, int]:
        legacy = common_path.LEGACY_APPLICATION_SETTINGS_FILE
        imported_legacy = False
        with Session(engine) as session, session.begin():
            row = session.get(ApplicationSettingsRecord, 1)
            if row is None:
                seed, interval, retention = 42, 1.0, 30
                if import_legacy and legacy.is_file():
                    try:
                        payload = json.loads(legacy.read_text(encoding="utf-8"))
                        if not isinstance(payload, dict):
                            raise ValueError("Expected a JSON object")
                        global_values = payload.get("global", {})
                        job_values = payload.get("jobs", {})
                        seed = int(global_values.get("seed", seed))
                        interval = float(job_values.get("polling_interval", interval))
                        retention = int(job_values.get("retention_days", retention))
                        if not math.isfinite(interval) or interval <= 0 or retention < 1:
                            raise ValueError("Application settings values are out of range")
                        imported_legacy = True
                    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                        raise DatabaseConfigurationError(f"Legacy application settings could not be imported: {exc}") from exc
                row = ApplicationSettingsRecord(
                    settings_id=1,
                    global_seed=seed,
                    jobs_polling_interval=interval,
                    jobs_retention_days=retention,
                    legacy_imported=imported_legacy,
                )
                session.add(row)
                session.flush()
            else:
                imported_legacy = bool(row.legacy_imported)
            values = (
                int(row.global_seed),
                float(row.jobs_polling_interval),
                int(row.jobs_retention_days),
            )
            if not math.isfinite(values[1]) or values[1] <= 0 or values[2] < 1:
                raise DatabaseConfigurationError(
                    "Application settings contain values outside their supported ranges"
                )
        if imported_legacy and legacy.is_file():
            try:
                legacy.unlink()
            except OSError:
                # The committed database row is the durable migration marker.
                pass
        return values

    # -------------------------------------------------------------------------
    def _remove_legacy_batch_setting(self) -> None:
        os.environ.pop("DATABASE_INSERT_BATCH_SIZE", None)
        env_file = common_path.ENV_FILE
        if not env_file.is_file():
            return
        content = env_file.read_text(encoding="utf-8")
        updated = re.sub(r"(?m)^\s*DATABASE_INSERT_BATCH_SIZE\s*=.*(?:\r?\n|$)", "", content)
        if updated == content:
            return
        temporary = env_file.with_suffix(env_file.suffix + ".tmp")
        temporary.write_text(updated, encoding="utf-8")
        os.replace(temporary, env_file)


database_runtime = DatabaseRuntime()
