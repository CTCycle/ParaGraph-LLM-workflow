from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy

from server.contracts.chat_history import ChatHistoryMessage
from server.configurations.settings import SQLiteSettings
from server.repositories.database.sqlite import SQLiteRepository
from server.repositories.schemas import Base
from server.repositories.workflow import chat_history_database as chat_history_module

###############################################################################
class InMemorySQLiteRepository(SQLiteRepository):

    # -------------------------------------------------------------------------
    def __init__(self) -> None:
        engine = sqlalchemy.create_engine("sqlite:///:memory:", future=True)
        super().__init__(
            SQLiteSettings(insert_batch_size=2), engine=engine, db_path=None
        )

###############################################################################
def test_database_chat_history_repository_accepts_injected_sqlite_repository() -> None:
    database_repository = InMemorySQLiteRepository()
    repository = chat_history_module.DatabaseChatHistoryRepository(database_repository)

    Base.metadata.create_all(database_repository.engine)

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

    repository.clear_session("workflow-a", "session-a")

    assert repository.get_messages("workflow-a", "session-a", "node-a") == []
    remaining = repository.get_messages("workflow-a", "session-b", "node-a")
    assert [message.content for message in remaining] == ["other"]
