from __future__ import annotations

from dataclasses import replace

import pytest

from server.domain.settings import (
    DatabaseSettings,
    GlobalSettings,
    JobsSettings,
    ServerSettings,
)
from server.repositories.configuration import ConfigurationRepository
from server.repositories.database.factory import DatabaseRepositoryFactory


def _database_settings(*, embedded: bool, engine: str | None) -> DatabaseSettings:
    return DatabaseSettings(
        embedded_database=embedded,
        engine=engine,
        host="localhost" if not embedded else None,
        port=5432 if not embedded else None,
        database_name="paragraph" if not embedded else None,
        username="paragraph" if not embedded else None,
        password="secret" if not embedded else None,
        ssl=False,
        ssl_ca=None,
        connect_timeout=30,
        insert_batch_size=1000,
    )


def _server_settings(database: DatabaseSettings) -> ServerSettings:
    return ServerSettings(
        database=database,
        global_settings=GlobalSettings(seed=42),
        jobs=JobsSettings(polling_interval=1.0),
    )


def test_configuration_repository_selects_sqlite_from_runtime_settings(
    monkeypatch,
) -> None:
    sqlite_settings = _database_settings(embedded=True, engine=None)

    class FakeFactory:
        def __init__(self) -> None:
            self.seen: list[DatabaseSettings] = []

        def build(self, settings: DatabaseSettings):
            self.seen.append(settings)
            return type("Repo", (), {"engine": object()})()

    factory = FakeFactory()
    repository = ConfigurationRepository(database_factory=factory)
    monkeypatch.setattr(
        "server.repositories.configuration.get_server_settings",
        lambda: _server_settings(sqlite_settings),
    )

    _ = repository._database_engine()  # noqa: SLF001

    assert factory.seen[0].embedded_database is True
    assert factory.seen[0].engine is None


def test_configuration_repository_selects_postgres_from_runtime_settings(
    monkeypatch,
) -> None:
    postgres_settings = _database_settings(embedded=False, engine="postgres")

    class FakeFactory:
        def __init__(self) -> None:
            self.seen: list[DatabaseSettings] = []

        def build(self, settings: DatabaseSettings):
            self.seen.append(settings)
            return type("Repo", (), {"engine": object()})()

    factory = FakeFactory()
    repository = ConfigurationRepository(database_factory=factory)
    monkeypatch.setattr(
        "server.repositories.configuration.get_server_settings",
        lambda: _server_settings(postgres_settings),
    )

    _ = repository._database_engine()  # noqa: SLF001

    assert factory.seen[0].embedded_database is False
    assert factory.seen[0].engine == "postgres"


def test_database_repository_factory_rejects_invalid_engine() -> None:
    settings = _database_settings(embedded=False, engine="mysql")
    factory = DatabaseRepositoryFactory()

    with pytest.raises(ValueError, match="Unsupported database engine"):
        _ = factory.build(settings)


def test_configuration_repository_reads_current_runtime_settings_each_call(
    monkeypatch,
) -> None:
    sqlite_settings = _database_settings(embedded=True, engine=None)
    postgres_settings = _database_settings(embedded=False, engine="postgresql")
    current_settings = {"database": sqlite_settings}

    class FakeFactory:
        def __init__(self) -> None:
            self.seen: list[DatabaseSettings] = []

        def build(self, settings: DatabaseSettings):
            self.seen.append(settings)
            return type("Repo", (), {"engine": object()})()

    factory = FakeFactory()
    repository = ConfigurationRepository(database_factory=factory)
    monkeypatch.setattr(
        "server.repositories.configuration.get_server_settings",
        lambda: _server_settings(current_settings["database"]),
    )

    _ = repository._database_engine()  # noqa: SLF001
    current_settings["database"] = replace(postgres_settings)
    _ = repository._database_engine()  # noqa: SLF001

    assert factory.seen[0].embedded_database is True
    assert factory.seen[1].embedded_database is False
    assert factory.seen[1].engine == "postgresql"
