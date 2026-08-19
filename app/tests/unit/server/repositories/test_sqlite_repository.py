from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import sqlalchemy
from sqlalchemy import inspect

from server.domain.settings import SQLiteSettings
from server.repositories.database import initializer as initializer_module
from server.repositories.database import sqlite as sqlite_module

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

    repository = sqlite_module.SQLiteRepository(_build_settings())

    assert repository.db_path == str(tmp_path / "database.db")

###############################################################################
def test_initialize_sqlite_database_creates_application_schema(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(sqlite_module.common_path, "RESOURCES_ROOT", tmp_path)

    initializer_module.initialize_sqlite_database(_build_settings())

    repository = sqlite_module.SQLiteRepository(_build_settings())
    assert set(inspect(repository.engine).get_table_names()) == {
        "access_keys",
        "chat_history_messages",
        "configuration_profiles",
        "execution_events",
        "execution_runs",
        "execution_steps",
        "nodes",
        "user_sessions",
    }

###############################################################################
def test_sqlite_repository_save_load_and_count_rows(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(sqlite_module.common_path, "RESOURCES_ROOT", tmp_path)
    repository = sqlite_module.SQLiteRepository(_build_settings())

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
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(sqlite_module.common_path, "RESOURCES_ROOT", tmp_path)
    repository = sqlite_module.SQLiteRepository(_build_settings())

    loaded = repository.load_from_database("missing_table")

    assert loaded.empty
    assert loaded.shape == (0, 0)

###############################################################################
def test_sqlite_repository_count_rows_raises_for_missing_table(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(sqlite_module.common_path, "RESOURCES_ROOT", tmp_path)
    repository = sqlite_module.SQLiteRepository(_build_settings())

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
