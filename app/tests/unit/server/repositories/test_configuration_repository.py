from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine

import server.repositories.configuration as configuration_module
from server.repositories.configuration import ConfigurationRepository
from server.repositories.database.configuration import DatabaseConfiguration
from server.repositories.database.runtime import DatabaseRuntime


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
