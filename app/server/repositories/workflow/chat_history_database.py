from __future__ import annotations

from datetime import timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from server.configurations.startup import get_server_settings
from server.domain.chat_history import ChatHistoryMessage
from server.repositories.database.factory import DatabaseRepositoryFactory
from server.repositories.schemas import Base, ChatHistoryMessageRecord

###############################################################################
class DatabaseChatHistoryRepository:
    def __init__(
        self, database_factory: DatabaseRepositoryFactory | None = None
    ) -> None:
        self._database_factory = database_factory or DatabaseRepositoryFactory()

    def _database_engine(self):
        settings = get_server_settings().database
        return self._database_factory.build(settings).engine

    def _ensure_table(self) -> None:
        Base.metadata.create_all(
            self._database_engine(), tables=[ChatHistoryMessageRecord.__table__]
        )

    def get_messages(
        self, workflow_id: str, execution_session_id: str, node_id: str
    ) -> list[ChatHistoryMessage]:
        self._ensure_table()
        with Session(self._database_engine()) as db_session:
            rows = list(
                db_session.execute(
                    select(ChatHistoryMessageRecord)
                    .where(
                        ChatHistoryMessageRecord.workflow_id == workflow_id,
                        ChatHistoryMessageRecord.execution_session_id
                        == execution_session_id,
                        ChatHistoryMessageRecord.node_id == node_id,
                    )
                    .order_by(ChatHistoryMessageRecord.chat_history_message_id.asc())
                ).scalars()
            )
            return [
                ChatHistoryMessage(
                    role=str(row.role),
                    content=str(row.content),
                    timestamp=(
                        row.created_at
                        if row.created_at.tzinfo is not None
                        else row.created_at.replace(tzinfo=timezone.utc)
                    ),
                )
                for row in rows
            ]

    def append_messages(
        self,
        workflow_id: str,
        execution_session_id: str,
        node_id: str,
        messages: list[ChatHistoryMessage],
    ) -> list[ChatHistoryMessage]:
        self._ensure_table()
        with Session(self._database_engine()) as db_session:
            for item in messages:
                timestamp = item.timestamp
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                db_session.add(
                    ChatHistoryMessageRecord(
                        workflow_id=workflow_id,
                        execution_session_id=execution_session_id,
                        node_id=node_id,
                        role=item.role,
                        content=item.content,
                        created_at=timestamp.astimezone(timezone.utc),
                    )
                )
            db_session.commit()
        return self.get_messages(workflow_id, execution_session_id, node_id)

    def clear_session(self, workflow_id: str, execution_session_id: str) -> None:
        self._ensure_table()
        with Session(self._database_engine()) as db_session:
            db_session.execute(
                delete(ChatHistoryMessageRecord).where(
                    ChatHistoryMessageRecord.workflow_id == workflow_id,
                    ChatHistoryMessageRecord.execution_session_id
                    == execution_session_id,
                )
            )
            db_session.commit()

    def set_messages(
        self,
        workflow_id: str,
        execution_session_id: str,
        node_id: str,
        messages: list[ChatHistoryMessage],
    ) -> None:
        self._ensure_table()
        with Session(self._database_engine()) as db_session:
            db_session.execute(
                delete(ChatHistoryMessageRecord).where(
                    ChatHistoryMessageRecord.workflow_id == workflow_id,
                    ChatHistoryMessageRecord.execution_session_id
                    == execution_session_id,
                    ChatHistoryMessageRecord.node_id == node_id,
                )
            )
            for item in messages:
                timestamp = item.timestamp
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                db_session.add(
                    ChatHistoryMessageRecord(
                        workflow_id=workflow_id,
                        execution_session_id=execution_session_id,
                        node_id=node_id,
                        role=item.role,
                        content=item.content,
                        created_at=timestamp.astimezone(timezone.utc),
                    )
                )
            db_session.commit()

    def reset_for_tests(self) -> None:
        try:
            self._ensure_table()
            with Session(self._database_engine()) as db_session:
                db_session.execute(delete(ChatHistoryMessageRecord))
                db_session.commit()
        except OperationalError:
            return


database_chat_history_repository = DatabaseChatHistoryRepository()

