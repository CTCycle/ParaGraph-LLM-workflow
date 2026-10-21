from __future__ import annotations

import json
import os
from pathlib import Path
import threading

import pytest
from sqlalchemy import create_engine, text

from server.common import path as common_path
from server.repositories.database.configuration import (
    DatabaseConfiguration,
    DatabaseConfigurationError,
    save_database_configuration,
)
from server.repositories.database.runtime import (
    DatabaseBusyError,
    DatabaseRuntime,
)
from server.repositories.schemas import ApplicationSettingsRecord


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
