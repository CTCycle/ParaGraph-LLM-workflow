from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine, text

import server.api.database as database_api
from server.common import path as common_path
from server.contracts.database import DatabaseConfigurationPayload
from server.repositories.database.runtime import DatabaseRuntime
import pytest


def _configure_runtime(runtime: DatabaseRuntime, monkeypatch, root: Path) -> None:
    monkeypatch.setattr(common_path, "RESOURCES_ROOT", root)
    monkeypatch.setattr(database_api, "database_runtime", runtime)


def test_database_endpoints_test_apply_and_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)
    _configure_runtime(runtime, monkeypatch, tmp_path)
    payload = {
        "backend": "sqlite",
        "database_path": "first.db",
        "insert_batch_size": 12,
    }
    typed_payload = DatabaseConfigurationPayload.model_validate(payload)

    status = database_api.get_database_configuration()
    assert status.connected is False

    tested = database_api.test_database_configuration(typed_payload)
    assert tested.ok is True

    applied = database_api.put_database_configuration(typed_payload)
    assert applied.connected is True
    active_path = runtime.status()["database_path"]

    incompatible = tmp_path / "incompatible.db"
    engine = create_engine(f"sqlite:///{incompatible.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE unrelated (value TEXT)"))
    engine.dispose()
    with pytest.raises(HTTPException) as failure:
        database_api.put_database_configuration(
            DatabaseConfigurationPayload(
                backend="sqlite",
                database_path=str(incompatible),
                insert_batch_size=12,
            )
        )
    assert failure.value.status_code == 503
    assert runtime.status()["database_path"] == active_path
    runtime.reset_for_tests()


def test_database_apply_rejects_an_active_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from server.services.jobs import job_manager

    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)
    _configure_runtime(runtime, monkeypatch, tmp_path)
    monkeypatch.setattr(job_manager, "is_job_running", lambda job_type=None: job_type == "workflow")

    with pytest.raises(HTTPException) as failure:
        database_api.put_database_configuration(
            DatabaseConfigurationPayload(
                backend="sqlite", database_path="blocked.db", insert_batch_size=9
            )
        )

    assert failure.value.status_code == 409
    assert "active workflow" in failure.value.detail
    assert runtime.status()["connected"] is False
    runtime.reset_for_tests()
