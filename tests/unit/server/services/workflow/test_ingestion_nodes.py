from __future__ import annotations

from pathlib import Path

from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from ParaGraph.server.services.workflow import node_registry
from ParaGraph.server.services.workflow.node_handlers import ingestion as ingestion_module


class FakeApiResponse:
    def __init__(self, url: str, payload: dict[str, object]) -> None:
        self.url = url
        self._payload = payload
        self.status_code = 200
        self.headers = {'content-type': 'application/json'}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload

    @property
    def text(self) -> str:
        return ''


def test_document_loader_accepts_multiple_files(tmp_path: Path) -> None:
    source_a = tmp_path / 'one.txt'
    source_b = tmp_path / 'two.md'
    source_a.write_text('alpha', encoding='utf-8')
    source_b.write_text('beta', encoding='utf-8')

    payload = node_registry.execute('DOCUMENT_LOADER', 1, {'file_paths': [str(source_a), str(source_b)]}, {})

    assert [document['text'] for document in payload['documents']] == ['alpha', 'beta']
    assert all(document['source_uri'].startswith(str(tmp_path)) for document in payload['documents'])



def test_load_documents_emits_deferred_records_without_eager_text(tmp_path: Path) -> None:
    source_dir = tmp_path / 'docs'
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / 'one.txt').write_text('alpha', encoding='utf-8')
    (source_dir / 'two.md').write_text('beta', encoding='utf-8')
    (source_dir / 'skip.bin').write_bytes(b'\x00\x01')

    payload = node_registry.execute(
        'LOAD_DOCUMENTS',
        1,
        {'folder_path': str(source_dir), 'recursive': False},
        {},
    )

    assert [Path(document['source_uri']).name for document in payload['documents']] == ['one.txt', 'two.md']
    assert all(document['text'] == '' for document in payload['documents'])
    assert all(document['metadata']['deferred_load'] is True for document in payload['documents'])


def test_load_documents_respects_recursive_toggle(tmp_path: Path) -> None:
    source_dir = tmp_path / 'collection'
    nested_dir = source_dir / 'nested'
    nested_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / 'root.txt').write_text('root', encoding='utf-8')
    (nested_dir / 'child.txt').write_text('child', encoding='utf-8')

    non_recursive = node_registry.execute(
        'LOAD_DOCUMENTS',
        1,
        {'folder_path': str(source_dir), 'recursive': False},
        {},
    )
    recursive = node_registry.execute(
        'LOAD_DOCUMENTS',
        1,
        {'folder_path': str(source_dir), 'recursive': True},
        {},
    )

    assert [Path(document['source_uri']).name for document in non_recursive['documents']] == ['root.txt']
    assert sorted(Path(document['source_uri']).name for document in recursive['documents']) == ['child.txt', 'root.txt']

def test_api_fetcher_caps_request_list_and_extracts_selected_json(monkeypatch) -> None:
    responses = {
        'https://api.test/first': {'payload': {'text': 'first'}},
        'https://api.test/second': {'payload': {'text': 'second'}},
    }

    def fake_get(url: str, timeout: float, follow_redirects: bool, headers: dict[str, str]):
        _ = timeout
        _ = follow_redirects
        _ = headers
        return FakeApiResponse(url, responses[url])

    monkeypatch.setattr(ingestion_module.httpx, 'get', fake_get)

    payload = node_registry.execute(
        'API_FETCHER',
        1,
        {
            'url': 'https://api.test/first',
            'request_urls': ['https://api.test/first', 'https://api.test/second'],
            'response_selector': 'payload.text',
            'max_calls': 2,
            'allow_concurrency': False,
        },
        {},
    )

    assert [document['text'] for document in payload['documents']] == ['first', 'second']
    assert payload['documents'][1]['metadata']['call_index'] == 1


def test_database_connection_and_query_roundtrip(tmp_path: Path) -> None:
    class NotesBase(DeclarativeBase):
        pass

    class Note(NotesBase):
        __tablename__ = 'notes'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        title: Mapped[str] = mapped_column(String, nullable=False)
        body: Mapped[str] = mapped_column(String, nullable=False)

    database_path = tmp_path / 'records.sqlite'
    engine = create_engine(f"sqlite:///{database_path}")
    NotesBase.metadata.create_all(engine)
    with Session(engine) as db_session:
        db_session.add_all(
            [
                Note(title='Alpha', body='First row'),
                Note(title='Beta', body='Second row'),
            ]
        )
        db_session.commit()
    engine.dispose()

    connection_payload = node_registry.execute(
        'DATABASE_CONNECTION',
        1,
        {'engine': 'sqlite', 'file_path': str(database_path), 'connect_timeout_s': 5},
        {},
    )
    query_payload = node_registry.execute(
        'DATABASE_QUERY',
        1,
        {'query_text': 'SELECT id, title, body FROM notes ORDER BY id', 'row_limit': 10},
        {'connection': connection_payload['connection']},
    )

    assert connection_payload['connection']['engine'] == 'sqlite'
    assert len(query_payload['records']) == 2
    assert query_payload['records'][0]['title'] == 'Alpha'
    assert 'First row' in query_payload['documents'][0]['text']


def test_database_query_rejects_non_read_only_statements(tmp_path: Path) -> None:
    class UnsafeNotesBase(DeclarativeBase):
        pass

    class UnsafeNote(UnsafeNotesBase):
        __tablename__ = 'notes'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        title: Mapped[str] = mapped_column(String, nullable=False)

    database_path = tmp_path / 'unsafe.sqlite'
    engine = create_engine(f"sqlite:///{database_path}")
    UnsafeNotesBase.metadata.create_all(engine)
    engine.dispose()

    connection_payload = node_registry.execute(
        'DATABASE_CONNECTION',
        1,
        {'engine': 'sqlite', 'file_path': str(database_path), 'connect_timeout_s': 5},
        {},
    )

    try:
        node_registry.execute(
            'DATABASE_QUERY',
            1,
            {'query_text': 'DELETE FROM notes', 'row_limit': 10},
            {'connection': connection_payload['connection']},
        )
    except ValueError as exc:
        assert 'read-only' in str(exc)
    else:
        raise AssertionError('Expected read-only validation failure for DELETE statement')


def test_database_query_rejects_mutating_cte_statement(tmp_path: Path) -> None:
    class CteNotesBase(DeclarativeBase):
        pass

    class CteNote(CteNotesBase):
        __tablename__ = 'notes'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        title: Mapped[str] = mapped_column(String, nullable=False)

    database_path = tmp_path / 'cte.sqlite'
    engine = create_engine(f"sqlite:///{database_path}")
    CteNotesBase.metadata.create_all(engine)
    engine.dispose()

    connection_payload = node_registry.execute(
        'DATABASE_CONNECTION',
        1,
        {'engine': 'sqlite', 'file_path': str(database_path), 'connect_timeout_s': 5},
        {},
    )

    with_statement = 'WITH moved AS (DELETE FROM notes RETURNING id) SELECT * FROM moved'
    try:
        node_registry.execute(
            'DATABASE_QUERY',
            1,
            {'query_text': with_statement, 'row_limit': 10},
            {'connection': connection_payload['connection']},
        )
    except ValueError as exc:
        assert 'mutating' in str(exc).lower()
    else:
        raise AssertionError('Expected read-only validation failure for mutating CTE statement')


def test_database_query_rejects_pragma_assignment(tmp_path: Path) -> None:
    class PragmaBase(DeclarativeBase):
        pass

    class PragmaNote(PragmaBase):
        __tablename__ = 'notes'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        title: Mapped[str] = mapped_column(String, nullable=False)

    database_path = tmp_path / 'pragma.sqlite'
    engine = create_engine(f"sqlite:///{database_path}")
    PragmaBase.metadata.create_all(engine)
    engine.dispose()

    connection_payload = node_registry.execute(
        'DATABASE_CONNECTION',
        1,
        {'engine': 'sqlite', 'file_path': str(database_path), 'connect_timeout_s': 5},
        {},
    )

    try:
        node_registry.execute(
            'DATABASE_QUERY',
            1,
            {'query_text': 'PRAGMA journal_mode = WAL', 'row_limit': 10},
            {'connection': connection_payload['connection']},
        )
    except ValueError as exc:
        assert 'assignment' in str(exc).lower() or 'not allowed' in str(exc).lower()
    else:
        raise AssertionError('Expected read-only validation failure for PRAGMA assignment')


def test_sql_file_database_node_roundtrip(tmp_path: Path) -> None:
    class ItemsBase(DeclarativeBase):
        pass

    class Item(ItemsBase):
        __tablename__ = 'items'
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        name: Mapped[str] = mapped_column(String, nullable=False)

    database_path = tmp_path / 'file_dataset.sqlite'
    engine = create_engine(f"sqlite:///{database_path}")
    ItemsBase.metadata.create_all(engine)
    with Session(engine) as db_session:
        db_session.add(Item(name='alpha'))
        db_session.commit()
    engine.dispose()

    connection_payload = node_registry.execute(
        'SQL_FILE_DATABASE',
        1,
        {
            'db_engine': 'sqlite',
            'db_path': str(database_path),
            'db_name': 'FAIRS',
            'db_user': 'postgres',
            'db_password': 'change_me',
            'db_ssl': False,
            'db_ssl_ca': '',
            'db_connect_timeout': 30,
        },
        {},
    )

    assert connection_payload['connection']['engine'] == 'sqlite'
    assert connection_payload['connection']['file_path'] == str(database_path.resolve())
    assert connection_payload['connection']['read_only'] is True
    assert connection_payload['connection']['database_name'] == 'FAIRS'


def test_sql_database_requires_required_fields_before_connect_attempt() -> None:
    try:
        node_registry.execute(
            'SQL_DATABASE',
            1,
            {
                'db_engine': 'postgres',
                'db_host': '',
                'db_port': 5432,
                'db_name': '',
                'db_user': 'postgres',
                'db_password': 'change_me',
                'db_ssl': False,
                'db_ssl_ca': '',
                'db_connect_timeout': 30,
            },
            {},
        )
    except ValueError as exc:
        message = str(exc)
        assert 'db_host' in message or 'db_name' in message
    else:
        raise AssertionError('Expected SQL_DATABASE validation failure for missing required fields')
