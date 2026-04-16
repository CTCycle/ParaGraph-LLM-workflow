from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ParaGraph.server.domain.settings import DatabaseSettings
from ParaGraph.server.repositories.database import sqlite as sqlite_module


def _build_settings() -> DatabaseSettings:
    return DatabaseSettings(
        embedded_database=True,
        engine=None,
        host=None,
        port=None,
        database_name=None,
        username=None,
        password=None,
        ssl=False,
        ssl_ca=None,
        connect_timeout=10,
        insert_batch_size=1000,
    )


def test_sqlite_repository_uses_resources_root_for_default_path(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(sqlite_module, "RESOURCES_PATH", str(tmp_path))

    repository = sqlite_module.SQLiteRepository(_build_settings())

    assert repository.db_path == str(tmp_path / "database.db")


def test_sqlite_repository_migrates_legacy_database_path(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(sqlite_module, "RESOURCES_PATH", str(tmp_path))

    legacy_dir = tmp_path / "database"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_db_path = legacy_dir / "database.db"
    legacy_db_path.write_bytes(b"legacy-data")

    repository = sqlite_module.SQLiteRepository(_build_settings())
    migrated_db_path = Path(repository.db_path or "")

    assert migrated_db_path == tmp_path / "database.db"
    assert migrated_db_path.exists()
    assert migrated_db_path.read_bytes() == b"legacy-data"
    assert not legacy_db_path.exists()


def test_sqlite_repository_save_load_and_count_rows(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(sqlite_module, "RESOURCES_PATH", str(tmp_path))
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


def test_sqlite_repository_load_missing_table_returns_empty_frame(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(sqlite_module, "RESOURCES_PATH", str(tmp_path))
    repository = sqlite_module.SQLiteRepository(_build_settings())

    loaded = repository.load_from_database("missing_table")

    assert loaded.empty
    assert loaded.shape == (0, 0)


def test_sqlite_repository_count_rows_raises_for_missing_table(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(sqlite_module, "RESOURCES_PATH", str(tmp_path))
    repository = sqlite_module.SQLiteRepository(_build_settings())

    with pytest.raises(ValueError, match="does not exist"):
        repository.count_rows("missing_table")
