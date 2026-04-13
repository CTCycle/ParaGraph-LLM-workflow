from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ParaGraph.server.domain.settings import DatabaseSettings
from ParaGraph.server.repositories.database import backend as backend_module


def _build_sqlite_settings() -> DatabaseSettings:
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


def _build_postgres_settings() -> DatabaseSettings:
    return DatabaseSettings(
        embedded_database=False,
        engine='postgres',
        host='localhost',
        port=5432,
        database_name='paragraph',
        username='postgres',
        password='postgres',
        ssl=False,
        ssl_ca=None,
        connect_timeout=10,
        insert_batch_size=1000,
    )


def test_build_backend_initializes_sqlite_only_when_database_file_missing(tmp_path: Path, monkeypatch) -> None:
    settings = _build_sqlite_settings()
    monkeypatch.setattr(backend_module, 'RESOURCES_PATH', str(tmp_path))
    monkeypatch.setattr(backend_module, 'get_server_settings', lambda: SimpleNamespace(database=settings))

    create_all_calls: list[object] = []

    def fake_create_all(engine: object) -> None:
        create_all_calls.append(engine)

    monkeypatch.setattr(backend_module.Base.metadata, 'create_all', fake_create_all)
    monkeypatch.setattr(
        backend_module,
        'build_sqlite_backend',
        lambda _settings: SimpleNamespace(engine=object(), db_path=str(tmp_path / 'database.db')),
    )
    monkeypatch.setitem(backend_module.BACKEND_FACTORIES, 'sqlite', backend_module.build_sqlite_backend)

    database = backend_module.ParaGraphDatabase()
    assert create_all_calls == [database.backend.engine]

    (tmp_path / 'database.db').write_text('existing', encoding='utf-8')
    create_all_calls.clear()

    database = backend_module.ParaGraphDatabase()
    assert create_all_calls == []
    assert database.backend is not None


def test_build_backend_never_initializes_postgres_on_startup(monkeypatch) -> None:
    settings = _build_postgres_settings()

    create_all_calls: list[object] = []

    def fake_create_all(engine: object) -> None:
        create_all_calls.append(engine)

    monkeypatch.setattr(backend_module.Base.metadata, 'create_all', fake_create_all)
    monkeypatch.setattr(
        backend_module,
        'build_postgres_backend',
        lambda _settings: SimpleNamespace(engine=object(), db_path=None),
    )
    monkeypatch.setitem(backend_module.BACKEND_FACTORIES, 'postgres', backend_module.build_postgres_backend)
    monkeypatch.setattr(backend_module, 'get_server_settings', lambda: SimpleNamespace(database=settings))

    database = backend_module.ParaGraphDatabase()

    assert create_all_calls == []
    assert database.backend is not None
