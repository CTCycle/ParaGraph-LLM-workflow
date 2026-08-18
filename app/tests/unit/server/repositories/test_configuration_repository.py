from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine

from server.domain.settings import SQLiteSettings
from server.repositories.configuration import ConfigurationRepository


###############################################################################
def test_configuration_repository_accepts_injected_sqlite_repository() -> None:
    engine = create_engine("sqlite:///:memory:")
    repository = ConfigurationRepository(
        database_repository=type("SQLiteRepositoryStub", (), {"engine": engine})()
    )

    assert repository._database_engine() is engine  # noqa: SLF001


###############################################################################
def test_configuration_repository_uses_the_embedded_sqlite_path(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "server.repositories.database.sqlite.common_path.RESOURCES_ROOT", tmp_path
    )
    monkeypatch.setattr(
        "server.repositories.configuration.get_server_settings",
        lambda: type(
            "ServerSettingsStub",
            (),
            {"database": SQLiteSettings(insert_batch_size=1000)},
        )(),
    )

    engine = ConfigurationRepository()._database_engine()  # noqa: SLF001

    assert engine.url.get_backend_name() == "sqlite"
    assert engine.url.database == str(tmp_path / "database.db")
