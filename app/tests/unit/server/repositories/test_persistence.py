from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine
import server.repositories.configuration as configuration_module
from server.repositories.configuration import ConfigurationRepository
from server.repositories.database.configuration import DatabaseConfiguration
from server.repositories.database.runtime import DatabaseRuntime
from concurrent.futures import ThreadPoolExecutor
import json
import shutil
import portalocker
import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy import inspect, text
from server.common import path as common_path
from server.configurations.settings import SQLiteSettings
from server.repositories.database import migration
from server.repositories.database.initializer import initialize_sqlite_database
from server.repositories.schemas import Base, ProviderConfiguration, UserSession
import os
import threading
from server.repositories.database.configuration import DatabaseConfigurationError, save_database_configuration
from server.repositories.database.runtime import DatabaseBusyError
from server.repositories.schemas import ApplicationSettingsRecord
import pandas as pd
import sqlalchemy
from server.repositories.database import initializer as initializer_module
from server.repositories.database import sqlite as sqlite_module
from server.repositories.schemas import ExecutionEventRecord, ExecutionRunRecord, ExecutionStepRecord

# Configuration repository

###############################################################################
def test_configuration_repository_accepts_injected_sqlite_repository() -> None:
    engine = create_engine("sqlite:///:memory:")
    repository = ConfigurationRepository(
        database_repository=type("SQLiteRepositoryStub", (), {"engine": engine})()
    )

    with repository._session() as session:  # noqa: SLF001
        assert session.get_bind() is engine

###############################################################################
def test_default_configuration_repository_tracks_the_active_database(
    tmp_path: Path, monkeypatch
) -> None:
    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)
    monkeypatch.setattr(configuration_module, "database_runtime", runtime)
    first = DatabaseConfiguration(database_path=str(tmp_path / "first.sqlite"))
    second = DatabaseConfiguration(database_path=str(tmp_path / "second.sqlite"), insert_batch_size=23)
    runtime.activate(first)
    with ConfigurationRepository()._session() as session:  # noqa: SLF001
        assert Path(session.get_bind().url.database).resolve() == first.resolved_path()
    runtime.activate(second)
    with ConfigurationRepository()._session() as session:  # noqa: SLF001
        assert Path(session.get_bind().url.database).resolve() == second.resolved_path()
    runtime.reset_for_tests()

# Database migrations

###############################################################################
def _settings() -> SQLiteSettings:
    return SQLiteSettings(insert_batch_size=1000)

###############################################################################
def _engine(database_path: Path) -> sa.Engine:
    return sa.create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"autocommit": False},
    )

###############################################################################
def _version(database_path: Path) -> str | None:
    engine = _engine(database_path)
    try:
        with engine.connect() as connection:
            if not inspect(connection).has_table("alembic_version"):
                return None
            return connection.execute(
                text("select version_num from alembic_version")
            ).scalar_one_or_none()
    finally:
        engine.dispose()

###############################################################################
def test_empty_database_is_created_and_migrated_to_head(tmp_path: Path) -> None:
    database_path = tmp_path / "database.db"

    initialize_sqlite_database(_settings(), db_path=database_path)
    initialize_sqlite_database(_settings(), db_path=database_path)

    engine = _engine(database_path)
    try:
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "application_settings",
            "chat_history_messages",
            "configuration_profiles",
            "execution_events",
            "execution_runs",
            "execution_steps",
            "provider_configurations",
            "user_sessions",
        }
        assert _version(database_path) == "0004_database_backed_application_settings"
    finally:
        engine.dispose()

###############################################################################
def test_migration_engine_enables_foreign_keys(tmp_path: Path) -> None:
    engine = migration._migration_engine(tmp_path / "foreign-keys.db")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()

###############################################################################
def test_populated_unversioned_schema_fails_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "unversioned.db"
    engine = _engine(database_path)
    Base.metadata.create_all(engine)
    with sa.orm.Session(engine) as session:
        session.add(
            UserSession(session_name="unversioned-session")
        )
        session.commit()
    engine.dispose()

    with pytest.raises(migration.DatabaseMigrationError, match="no Alembic revision"):
        initialize_sqlite_database(_settings(), db_path=database_path)

    engine = _engine(database_path)
    try:
        assert _version(database_path) is None
        assert "user_sessions" in inspect(engine).get_table_names()
    finally:
        engine.dispose()

###############################################################################
def test_partial_unversioned_schema_fails_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "partial.db"
    engine = _engine(database_path)
    Base.metadata.tables["user_sessions"].create(engine)
    engine.dispose()

    with pytest.raises(migration.DatabaseMigrationError, match="no Alembic revision"):
        initialize_sqlite_database(_settings(), db_path=database_path)

    engine = _engine(database_path)
    try:
        assert "alembic_version" not in inspect(engine).get_table_names()
        assert "user_sessions" in inspect(engine).get_table_names()
    finally:
        engine.dispose()

###############################################################################
def test_0002_schema_migrates_provider_data_to_canonical_shape(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "provider-migration.db"
    _apply_revision(database_path, "0002_remove_node_configuration_mirror")

    engine = _engine(database_path)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO user_sessions "
                "(session_name, ollama_base_url, ollama_chat_model, "
                "ollama_embedding_model, created_at, updated_at) "
                "VALUES (:session_name, :ollama_base_url, :ollama_chat_model, "
                ":ollama_embedding_model, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "session_name": "migrated-session",
                "ollama_base_url": "http://localhost:11434",
                "ollama_chat_model": "llama3.2",
                "ollama_embedding_model": "nomic-embed-text",
            },
        )
        session_id = connection.execute(
            text(
                "SELECT session_id FROM user_sessions "
                "WHERE session_name = 'migrated-session'"
            )
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO access_keys "
                "(session_id, provider, api_key, base_url, metadata_json, "
                "created_at, updated_at) "
                "VALUES (:session_id, 'openai', 'sk-test', NULL, :metadata, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"session_id": session_id, "metadata": json.dumps({})},
        )
        connection.execute(
            text(
                "INSERT INTO configuration_profiles "
                "(session_id, profile_name, configuration_json, created_at, updated_at) "
                "VALUES (:session_id, 'workbench', :configuration_json, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "session_id": session_id,
                "configuration_json": json.dumps(
                    {
                        "session_name": "migrated-session",
                        "access_keys": [
                            {
                                "provider": "openai",
                                "api_key": "sk-profile",
                                "base_url": None,
                                "metadata": {},
                            }
                        ],
                        "ollama": {
                            "base_url": "http://localhost:11434",
                            "chat_model": "llama3.2",
                            "embedding_model": "nomic-embed-text",
                        },
                    },
                    separators=(",", ":"),
                ),
            },
        )
    engine.dispose()

    initialize_sqlite_database(_settings(), db_path=database_path)

    engine = _engine(database_path)
    try:
        assert _version(database_path) == "0004_database_backed_application_settings"
        assert "access_keys" not in inspect(engine).get_table_names()
        columns = {
            column["name"] for column in inspect(engine).get_columns("user_sessions")
        }
        assert not {
            "ollama_base_url",
            "ollama_chat_model",
            "ollama_embedding_model",
        }.intersection(columns)
        with engine.connect() as connection:
            providers = {
                row.provider: row
                for row in connection.execute(
                    text(
                        "SELECT provider, api_key, base_url, metadata_json "
                        "FROM provider_configurations "
                        "WHERE session_id = :session_id"
                    ),
                    {"session_id": session_id},
                ).mappings()
            }
            assert providers["openai"]["api_key"] == "sk-test"
            assert providers["ollama"]["base_url"] == "http://localhost:11434"
            assert json.loads(providers["ollama"]["metadata_json"])["chat_model"] == (
                "llama3.2"
            )
            profile = connection.execute(
                text(
                    "SELECT configuration_json FROM configuration_profiles "
                    "WHERE profile_name = 'workbench'"
                )
            ).scalar_one()
            profile_payload = json.loads(profile)
            assert "access_keys" not in profile_payload
            assert "ollama" not in profile_payload
            assert {item["provider"] for item in profile_payload["provider_configurations"]} == {
                "openai",
                "ollama",
            }
    finally:
        engine.dispose()

###############################################################################
def test_unknown_revision_fails_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "unknown-revision.db"
    initialize_sqlite_database(_settings(), db_path=database_path)
    engine = _engine(database_path)
    with engine.begin() as connection:
        connection.execute(
            text("update alembic_version set version_num = 'unknown_revision'")
        )
    engine.dispose()

    with pytest.raises(migration.DatabaseMigrationError, match="ancestor"):
        initialize_sqlite_database(_settings(), db_path=database_path)

###############################################################################
def test_versioned_partial_schema_fails_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "versioned-partial.db"
    initialize_sqlite_database(_settings(), db_path=database_path)
    engine = _engine(database_path)
    with engine.begin() as connection:
        connection.execute(text("drop table execution_events"))
    engine.dispose()

    with pytest.raises(migration.DatabaseMigrationError, match="incomplete"):
        initialize_sqlite_database(_settings(), db_path=database_path)

###############################################################################
def test_multiple_database_heads_fail_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "multiple-heads.db"
    initialize_sqlite_database(_settings(), db_path=database_path)
    engine = _engine(database_path)
    with engine.begin() as connection:
        connection.execute(
            text("insert into alembic_version (version_num) values ('other_head')")
        )
    engine.dispose()

    with pytest.raises(migration.DatabaseMigrationError, match="multiple"):
        initialize_sqlite_database(_settings(), db_path=database_path)

###############################################################################
def _configure_revision_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source_root = common_path.SERVER_ROOT / "migrations"
    migration_root = tmp_path / "migrations"
    shutil.copytree(source_root, migration_root)
    (tmp_path / "pyproject.toml").write_text(
        "[tool.alembic]\n"
        'script_location = "%(here)s/migrations"\n'
        'prepend_sys_path = ["%(here)s/.."]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(common_path, "SERVER_ROOT", tmp_path)
    return migration_root

###############################################################################
def _add_marker_revision(migration_root: Path, *, failing: bool = False) -> None:
    (migration_root / "versions" / "0002_marker.py").write_text(
        '''"""Add a marker column for migration integration tests."""\n\n'''
        "from alembic import op\n"
        "import sqlalchemy as sa\n\n"
        "revision = '0005_marker'\n"
        "down_revision = '0004_database_backed_application_settings'\n"
        "branch_labels = None\n"
        "depends_on = None\n\n"
        "def upgrade():\n"
        "    op.add_column('user_sessions', sa.Column('migration_marker', sa.String(), nullable=True))\n\n"
        "def downgrade():\n"
        "    with op.batch_alter_table('user_sessions') as batch_op:\n"
        "        batch_op.drop_column('migration_marker')\n",
        encoding="utf-8",
    )
    if failing:
        (migration_root / "versions" / "0003_failure.py").write_text(
            '''"""Fail after issuing DDL to verify rollback."""\n\n'''
            "from alembic import op\n"
            "import sqlalchemy as sa\n\n"
            "revision = '0006_failure'\n"
            "down_revision = '0005_marker'\n"
            "branch_labels = None\n"
            "depends_on = None\n\n"
            "def upgrade():\n"
            "    op.add_column('user_sessions', sa.Column('failure_marker', sa.String(), nullable=True))\n"
            "    raise RuntimeError('intentional migration failure')\n\n"
            "def downgrade():\n"
            "    pass\n",
            encoding="utf-8",
        )

###############################################################################
def _apply_revision(
    database_path: Path, revision: str, *, downgrade: bool = False
) -> None:
    config = migration._alembic_config(database_path)
    engine = migration._migration_engine(database_path)
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            if downgrade:
                command.downgrade(config, revision)
            else:
                command.upgrade(config, revision)
    finally:
        engine.dispose()

###############################################################################
def test_outdated_database_is_upgraded_to_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migration_root = _configure_revision_tree(tmp_path / "project", monkeypatch)
    _add_marker_revision(migration_root)
    database_path = tmp_path / "outdated.db"

    initialize_sqlite_database(_settings(), db_path=database_path)
    engine = _engine(database_path)
    with sa.orm.Session(engine) as session:
        session.add(
            UserSession(
                session_name="behind-session",
                provider_configurations=[
                    ProviderConfiguration(
                        provider="ollama",
                        base_url="http://localhost:11434",
                        metadata_json={
                            "chat_model": "llama3.2",
                            "embedding_model": "nomic-embed-text",
                        },
                    )
                ],
            )
        )
        session.commit()
    engine.dispose()

    _apply_revision(database_path, "0001_initial", downgrade=True)
    initialize_sqlite_database(_settings(), db_path=database_path)

    engine = _engine(database_path)
    try:
        assert _version(database_path) == "0005_marker"
        assert "migration_marker" in {
            column["name"] for column in inspect(engine).get_columns("user_sessions")
        }
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("select session_name from user_sessions")
                ).scalar_one()
                == "behind-session"
            )
    finally:
        engine.dispose()

###############################################################################
def test_failed_migration_rolls_back_ddl_and_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migration_root = _configure_revision_tree(tmp_path / "project", monkeypatch)
    _add_marker_revision(migration_root, failing=True)
    database_path = tmp_path / "rollback.db"

    _apply_revision(database_path, "0005_marker")

    with pytest.raises(migration.DatabaseMigrationError, match="failed"):
        migration.run_database_migrations(database_path)

    engine = _engine(database_path)
    try:
        columns = {
            column["name"] for column in inspect(engine).get_columns("user_sessions")
        }
        assert "failure_marker" not in columns
        assert _version(database_path) == "0005_marker"
    finally:
        engine.dispose()

###############################################################################
def test_concurrent_initialization_is_serialized(tmp_path: Path) -> None:
    database_path = tmp_path / "concurrent.db"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                initialize_sqlite_database,
                _settings(),
                db_path=database_path,
            )
            for _ in range(2)
        ]
        for future in futures:
            future.result()

    assert _version(database_path) == "0004_database_backed_application_settings"

###############################################################################
def test_migration_lock_timeout_is_reported_as_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "locked.db"
    lock_path = database_path.with_name("locked.db.migration.lock")
    held_lock = portalocker.Lock(str(lock_path), mode="a", timeout=0)
    held_lock.acquire()
    monkeypatch.setattr(migration, "MIGRATION_LOCK_TIMEOUT_SECONDS", 0.01)
    try:
        with pytest.raises(migration.DatabaseMigrationError, match="Timed out"):
            migration.run_database_migrations(database_path)
    finally:
        held_lock.release()

# Database runtime

###############################################################################
def test_database_configuration_schema_is_strict_sqlite_only() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DatabaseConfiguration.model_validate(
            {"backend": "postgresql", "database_path": "db", "insert_batch_size": 2}
        )
    with pytest.raises(ValidationError):
        DatabaseConfiguration.model_validate(
            {"backend": "sqlite", "database_path": "db", "insert_batch_size": 2, "password": "secret"}
        )
    with pytest.raises(ValidationError):
        DatabaseConfiguration.model_validate(
            {"backend": "sqlite", "database_path": "", "insert_batch_size": 2}
        )

###############################################################################
def test_runtime_ignores_database_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    env_path = settings_dir / ".env"
    env_path.write_text("LLM_TIMEOUT_S=41\n", encoding="utf-8")
    env_example = settings_dir / ".env.example"
    env_example.write_text("LLM_TIMEOUT_S=30\n", encoding="utf-8")
    legacy_file = settings_dir / "configurations.json"
    monkeypatch.setattr(common_path, "RESOURCES_ROOT", tmp_path)
    monkeypatch.setattr(common_path, "ENV_FILE", env_path)
    monkeypatch.setattr(common_path, "ENV_EXAMPLE_FILE", env_example)
    monkeypatch.setattr(common_path, "LEGACY_APPLICATION_SETTINGS_FILE", legacy_file)
    monkeypatch.setenv("DATABASE_INSERT_BATCH_SIZE", "7")
    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)
    try:
        runtime.initialize()
        assert runtime.settings.database.insert_batch_size == 1000
        assert "DATABASE_INSERT_BATCH_SIZE" not in os.environ
    finally:
        runtime.reset_for_tests()

###############################################################################
def test_database_configuration_write_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import server.repositories.database.configuration as configuration_module

    existing = DatabaseConfiguration(database_path="old.db", insert_batch_size=19)
    replacement = DatabaseConfiguration(database_path="new.db", insert_batch_size=29)
    save_database_configuration(existing, tmp_path)
    original_bytes = (tmp_path / "database_config.json").read_bytes()

    def fail_replace(_source: object, _destination: object) -> None:
        raise OSError("controlled replace failure")

    monkeypatch.setattr(configuration_module.os, "replace", fail_replace)
    with pytest.raises(DatabaseConfigurationError, match="Could not save"):
        save_database_configuration(replacement, tmp_path)

    assert (tmp_path / "database_config.json").read_bytes() == original_bytes
    assert not list(tmp_path.glob("*.tmp"))

###############################################################################
def test_bootstrap_imports_legacy_values_once_and_restart_persists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_dir = tmp_path / "settings"
    env_dir.mkdir()
    env_file = env_dir / ".env"
    env_example = env_dir / ".env.example"
    env_file.write_text(
        "PARAGRAPH_RESOURCES_DIR=\nDATABASE_INSERT_BATCH_SIZE=29\nLLM_TIMEOUT_S=40\n",
        encoding="utf-8",
    )
    env_example.write_text("LLM_TIMEOUT_S=30\n", encoding="utf-8")
    legacy_file = env_dir / "configurations.json"
    legacy_file.write_text(
        json.dumps({"global": {"seed": 73}, "jobs": {"polling_interval": 2.5, "retention_days": 9}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(common_path, "RESOURCES_ROOT", tmp_path)
    monkeypatch.setattr(common_path, "ENV_FILE", env_file)
    monkeypatch.setattr(common_path, "ENV_EXAMPLE_FILE", env_example)
    monkeypatch.setattr(common_path, "LEGACY_APPLICATION_SETTINGS_FILE", legacy_file)
    monkeypatch.setenv("PARAGRAPH_RESOURCES_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_INSERT_BATCH_SIZE", "7")
    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)

    try:
        assert DatabaseConfiguration().resolved_path() == (tmp_path / "database.db").resolve()
        runtime.initialize()
        assert runtime.settings.database.insert_batch_size == 29
        assert runtime.settings.global_settings.seed == 73
        assert runtime.settings.jobs.polling_interval == 2.5
        assert runtime.settings.jobs.retention_days == 9
        assert not legacy_file.exists()
        assert "DATABASE_INSERT_BATCH_SIZE" not in env_file.read_text(encoding="utf-8")

        runtime.reset_for_tests()
        restarted = DatabaseRuntime(persist_configuration=False, publish_settings=False)
        restarted.initialize()
        assert restarted.settings.global_settings.seed == 73
        assert restarted.settings.jobs.retention_days == 9
        restarted.reset_for_tests()
    finally:
        runtime.reset_for_tests()

###############################################################################
def test_failed_legacy_settings_import_keeps_source_and_rolls_back_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    env_file = settings_dir / ".env"
    env_file.write_text("", encoding="utf-8")
    env_example = settings_dir / ".env.example"
    env_example.write_text("", encoding="utf-8")
    legacy_file = settings_dir / "configurations.json"
    legacy_file.write_text(
        json.dumps({"global": {"seed": 73}, "jobs": {"polling_interval": 0}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(common_path, "RESOURCES_ROOT", tmp_path)
    monkeypatch.setattr(common_path, "ENV_FILE", env_file)
    monkeypatch.setattr(common_path, "ENV_EXAMPLE_FILE", env_example)
    monkeypatch.setattr(common_path, "LEGACY_APPLICATION_SETTINGS_FILE", legacy_file)
    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)

    with pytest.raises(DatabaseConfigurationError, match="values are out of range"):
        runtime.initialize()

    assert legacy_file.exists()
    assert runtime.status()["connected"] is False
    engine = create_engine(f"sqlite:///{(tmp_path / 'database.db').as_posix()}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT COUNT(*) FROM application_settings")
            ).scalar_one() == 0
    finally:
        engine.dispose()
        runtime.reset_for_tests()

###############################################################################
def test_switching_databases_keeps_application_settings_isolated(
    tmp_path: Path,
) -> None:
    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)
    first = DatabaseConfiguration(database_path=str(tmp_path / "first.db"), insert_batch_size=8)
    second = DatabaseConfiguration(database_path=str(tmp_path / "second.db"), insert_batch_size=16)
    try:
        runtime.activate(first)
        with runtime.session() as session, session.begin():
            session.get(ApplicationSettingsRecord, 1).global_seed = 101
        runtime.activate(second)
        assert runtime.settings.global_settings.seed == 42
        with runtime.session() as session, session.begin():
            session.get(ApplicationSettingsRecord, 1).global_seed = 202
        runtime.activate(first)
        assert runtime.settings.global_settings.seed == 101
        runtime.activate(second)
        assert runtime.settings.global_settings.seed == 202
    finally:
        runtime.reset_for_tests()

###############################################################################
def test_failed_target_and_active_workflow_leave_current_database_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from server.services.jobs import job_manager

    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)
    first = DatabaseConfiguration(database_path=str(tmp_path / "active.db"))
    runtime.activate(first)
    original_path = runtime.status()["database_path"]
    incompatible = tmp_path / "incompatible.db"
    engine = create_engine(f"sqlite:///{incompatible.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE unmanaged (value TEXT)"))
    engine.dispose()

    with pytest.raises(DatabaseConfigurationError):
        runtime.test(DatabaseConfiguration(database_path=str(incompatible)))
    with pytest.raises(Exception):
        runtime.activate(DatabaseConfiguration(database_path=str(incompatible)))
    assert runtime.status()["database_path"] == original_path

    monkeypatch.setattr(job_manager, "is_job_running", lambda job_type=None: job_type == "workflow")
    with pytest.raises(DatabaseBusyError, match="active workflow"):
        runtime.activate(DatabaseConfiguration(database_path=str(tmp_path / "blocked.db")))
    assert runtime.status()["database_path"] == original_path
    runtime.reset_for_tests()

###############################################################################
def test_switch_waits_for_existing_repository_sessions(tmp_path: Path) -> None:
    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)
    first = DatabaseConfiguration(database_path=str(tmp_path / "current.db"))
    second = DatabaseConfiguration(database_path=str(tmp_path / "next.db"))
    entered = threading.Event()
    release = threading.Event()
    switched = threading.Event()

    runtime.activate(first)

    def hold_session() -> None:
        with runtime.session():
            entered.set()
            assert release.wait(timeout=5)

    def switch() -> None:
        runtime.activate(second)
        switched.set()

    operation = threading.Thread(target=hold_session)
    transition = threading.Thread(target=switch)
    operation.start()
    assert entered.wait(timeout=2)
    transition.start()
    assert not switched.wait(timeout=0.1)
    release.set()
    operation.join(timeout=3)
    transition.join(timeout=3)
    assert switched.is_set()
    assert runtime.status()["database_path"] == str(second.resolved_path())
    runtime.reset_for_tests()

###############################################################################
def test_switch_waits_for_multi_step_operations(tmp_path: Path) -> None:
    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)
    runtime.activate(DatabaseConfiguration(database_path=str(tmp_path / "current.db")))
    entered = threading.Event()
    release = threading.Event()
    switched = threading.Event()

    def hold_operation() -> None:
        with runtime.operation():
            entered.set()
            assert release.wait(timeout=5)

    def switch() -> None:
        runtime.activate(DatabaseConfiguration(database_path=str(tmp_path / "next.db")))
        switched.set()

    operation = threading.Thread(target=hold_operation)
    transition = threading.Thread(target=switch)
    operation.start()
    assert entered.wait(timeout=2)
    transition.start()
    assert not switched.wait(timeout=0.1)
    release.set()
    operation.join(timeout=3)
    transition.join(timeout=3)
    assert switched.is_set()
    runtime.reset_for_tests()

###############################################################################
def test_switch_rejects_workflow_admitted_during_drain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from server.services.jobs import job_manager

    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)
    first = DatabaseConfiguration(database_path=str(tmp_path / "current.db"))
    second = DatabaseConfiguration(database_path=str(tmp_path / "next.db"))
    operation_entered = threading.Event()
    release_operation = threading.Event()
    initial_job_check = threading.Event()
    job_running = threading.Event()
    rejected = threading.Event()
    runtime.activate(first)

    def is_job_running(job_type: str | None = None) -> bool:
        initial_job_check.set()
        return job_type == "workflow" and job_running.is_set()

    monkeypatch.setattr(job_manager, "is_job_running", is_job_running)

    def admit_workflow() -> None:
        with runtime.operation():
            operation_entered.set()
            assert release_operation.wait(timeout=5)

    def switch() -> None:
        try:
            runtime.activate(second)
        except DatabaseBusyError:
            rejected.set()

    operation = threading.Thread(target=admit_workflow)
    transition = threading.Thread(target=switch)
    operation.start()
    assert operation_entered.wait(timeout=2)
    transition.start()
    assert initial_job_check.wait(timeout=2)
    job_running.set()
    release_operation.set()
    operation.join(timeout=3)
    transition.join(timeout=3)

    assert rejected.is_set()
    assert runtime.status()["database_path"] == str(first.resolved_path())
    runtime.reset_for_tests()

# SQLite repository

###############################################################################
def _build_settings() -> SQLiteSettings:
    return SQLiteSettings(insert_batch_size=1000)

###############################################################################
def _build_memory_repository() -> sqlite_module.SQLiteRepository:
    return sqlite_module.SQLiteRepository(
        SQLiteSettings(insert_batch_size=2),
        engine=sqlalchemy.create_engine("sqlite:///:memory:", future=True),
    )

###############################################################################
def test_sqlite_repository_uses_resources_root_for_default_path(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(sqlite_module.common_path, "RESOURCES_ROOT", tmp_path)
    save_database_configuration(
        DatabaseConfiguration(database_path="selected.sqlite", insert_batch_size=27),
        tmp_path,
    )

    repository = sqlite_module.SQLiteRepository(_build_settings())

    assert repository.db_path == str(tmp_path / "selected.sqlite")
    assert repository.insert_batch_size == 27

###############################################################################
def test_initialize_sqlite_database_creates_application_schema(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(sqlite_module.common_path, "RESOURCES_ROOT", tmp_path)
    save_database_configuration(DatabaseConfiguration(), tmp_path)

    initializer_module.initialize_sqlite_database(_build_settings())

    repository = sqlite_module.SQLiteRepository(_build_settings())
    assert set(inspect(repository.engine).get_table_names()) == {
        "alembic_version",
        "application_settings",
        "chat_history_messages",
        "configuration_profiles",
        "execution_events",
        "execution_runs",
        "execution_steps",
        "provider_configurations",
        "user_sessions",
    }

###############################################################################
def test_sqlite_repository_enables_foreign_keys() -> None:
    repository = _build_memory_repository()

    with repository.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1

###############################################################################
def test_sqlite_repository_cascades_execution_children() -> None:
    repository = _build_memory_repository()
    Base.metadata.create_all(repository.engine)

    with repository.session() as db_session:
        db_session.add(
            ExecutionRunRecord(
                run_id="run-1",
                plan_id="plan-1",
                plan_json={},
                status="completed",
                progress=1.0,
                outputs_json={},
                cancellation_requested=False,
            )
        )
        db_session.commit()

        db_session.add_all(
            [
                ExecutionStepRecord(
                    run_id="run-1",
                    step_id="step-1",
                    node_id="node-1",
                    node_type="test",
                    position=0,
                    status="completed",
                    attempt_count=1,
                    output_json={},
                ),
                ExecutionEventRecord(
                    run_id="run-1",
                    sequence=1,
                    event_type="execution.completed",
                    payload_json={},
                ),
            ]
        )
        db_session.commit()

        run = db_session.get(ExecutionRunRecord, "run-1")
        assert run is not None
        db_session.delete(run)
        db_session.commit()

        assert db_session.query(ExecutionStepRecord).count() == 0
        assert db_session.query(ExecutionEventRecord).count() == 0

###############################################################################
def test_sqlite_repository_save_load_and_count_rows(
    tmp_path: Path,
) -> None:
    repository = sqlite_module.SQLiteRepository(
        _build_settings(), db_path=str(tmp_path / "database.db")
    )

    frame = pd.DataFrame(
        [
            {"name": "dataset-a", "created_at": "2026-03-20T10:00:00Z"},
            {"name": "dataset-b", "created_at": "2026-03-21T11:00:00Z"},
        ]
    )
    repository.save_into_database(frame, "datasets")

    loaded = repository.load_from_database("datasets")
    assert list(loaded["name"]) == ["dataset-a", "dataset-b"]
    assert repository.count_rows("datasets") == 2

###############################################################################
def test_sqlite_repository_load_missing_table_returns_empty_frame(
    tmp_path: Path,
) -> None:
    repository = sqlite_module.SQLiteRepository(
        _build_settings(), db_path=str(tmp_path / "database.db")
    )

    loaded = repository.load_from_database("missing_table")

    assert loaded.empty
    assert loaded.shape == (0, 0)

###############################################################################
def test_sqlite_repository_count_rows_raises_for_missing_table(
    tmp_path: Path,
) -> None:
    repository = sqlite_module.SQLiteRepository(
        _build_settings(), db_path=str(tmp_path / "database.db")
    )

    with pytest.raises(ValueError, match="does not exist"):
        repository.count_rows("missing_table")

###############################################################################
def test_sqlite_repository_save_load_and_count_dynamic_table() -> None:
    repository = _build_memory_repository()
    frame = pd.DataFrame(
        [
            {"name": "dataset-a", "row_count": 10, "score": 0.75, "enabled": True},
            {"name": "dataset-b", "row_count": 12, "score": 0.9, "enabled": False},
        ]
    )

    repository.save_into_database(frame, "dynamic_datasets")

    loaded = repository.load_from_database("dynamic_datasets")
    assert repository.count_rows("dynamic_datasets") == 2
    assert list(loaded.columns) == ["name", "row_count", "score", "enabled"]
    assert len(loaded) == 2

###############################################################################
def test_sqlite_repository_save_replaces_existing_dynamic_table_rows() -> None:
    repository = _build_memory_repository()
    repository.save_into_database(
        pd.DataFrame([{"name": "old-a", "value": 1}, {"name": "old-b", "value": 2}]),
        "replaceable_datasets",
    )
    repository.save_into_database(
        pd.DataFrame([{"name": "new-a", "value": 3}]), "replaceable_datasets"
    )

    loaded = repository.load_from_database("replaceable_datasets")
    assert repository.count_rows("replaceable_datasets") == 1
    assert loaded.to_dict(orient="records") == [{"name": "new-a", "value": 3}]
