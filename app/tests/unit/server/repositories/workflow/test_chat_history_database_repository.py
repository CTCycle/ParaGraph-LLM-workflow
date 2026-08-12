from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy

from server.domain.chat_history import ChatHistoryMessage
from server.domain.settings import DatabaseSettings
from server.repositories.database.base import TabularDatabaseRepository
from server.repositories.schemas import Base
from server.repositories.workflow import chat_history_database as chat_history_module

###############################################################################
class InMemoryTabularRepository(TabularDatabaseRepository):

    # -------------------------------------------------------------------------
    def __init__(self) -> None:
        engine = sqlalchemy.create_engine("sqlite:///:memory:", future=True)
        super().__init__(
            engine=engine,
            db_path=None,
            insert_batch_size=2,
        )

###############################################################################
class FakeDatabaseFactory:

    # -------------------------------------------------------------------------
    def __init__(self, repository: InMemoryTabularRepository) -> None:
        self.repository = repository
        self.build_calls = 0

    # -------------------------------------------------------------------------
    def build(self, settings: DatabaseSettings) -> InMemoryTabularRepository:
        self.build_calls += 1
        return self.repository

###############################################################################
class FakeServerSettings:

    # -------------------------------------------------------------------------
    def __init__(self) -> None:
        self.database = DatabaseSettings(
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
            insert_batch_size=2,
        )

###############################################################################
def test_database_chat_history_repository_builds_database_once(monkeypatch) -> None:
    database_repository = InMemoryTabularRepository()
    database_factory = FakeDatabaseFactory(database_repository)
    monkeypatch.setattr(
        chat_history_module,
        "get_server_settings",
        lambda: FakeServerSettings(),
    )

    repository = chat_history_module.DatabaseChatHistoryRepository(database_factory)

    Base.metadata.create_all(database_repository.engine)

    assert database_factory.build_calls == 1

    first_message = ChatHistoryMessage(
        role="user",
        content="first",
        timestamp=datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc),
    )
    second_message = ChatHistoryMessage(
        role="assistant",
        content="second",
        timestamp=datetime(2026, 5, 11, 8, 1, tzinfo=timezone.utc),
    )
    other_message = ChatHistoryMessage(
        role="user",
        content="other",
        timestamp=datetime(2026, 5, 11, 8, 2, tzinfo=timezone.utc),
    )

    repository.append_messages("workflow-a", "session-a", "node-a", [first_message])
    repository.append_messages("workflow-a", "session-a", "node-a", [second_message])
    repository.append_messages("workflow-a", "session-b", "node-a", [other_message])

    messages = repository.get_messages("workflow-a", "session-a", "node-a")
    assert [message.content for message in messages] == ["first", "second"]
    assert database_factory.build_calls == 1

    repository.clear_session("workflow-a", "session-a")

    assert repository.get_messages("workflow-a", "session-a", "node-a") == []
    remaining = repository.get_messages("workflow-a", "session-b", "node-a")
    assert [message.content for message in remaining] == ["other"]
    assert database_factory.build_calls == 1
