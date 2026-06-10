from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from server.configurations.startup import get_server_settings
from server.domain.chat_history import ChatHistoryMessage
from server.repositories.database.factory import DatabaseRepositoryFactory
from server.repositories.schemas import Base, ChatHistoryMessageRecord

###############################################################################
def _as_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)

###############################################################################
class DatabaseChatHistoryRepository:

    # -------------------------------------------------------------------------
    def __init__(
        self, database_factory: DatabaseRepositoryFactory | None = None
    ) -> None:
        self._database_factory = database_factory or DatabaseRepositoryFactory()
        self._database_repository = self._database_factory.build(
            get_server_settings().database
        )

    # -------------------------------------------------------------------------
    def _ensure_table(self) -> None:
        Base.metadata.create_all(
            self._database_repository.engine,
            tables=[ChatHistoryMessageRecord.__table__],
        )

    # -------------------------------------------------------------------------
    def get_messages(
        self, workflow_id: str, execution_session_id: str, node_id: str
    ) -> list[ChatHistoryMessage]:
        self._ensure_table()
        with Session(self._database_repository.engine) as db_session:
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
                    timestamp=_as_utc(row.created_at),
                )
                for row in rows
            ]

    # -------------------------------------------------------------------------
    def append_messages(
        self,
        workflow_id: str,
        execution_session_id: str,
        node_id: str,
        messages: list[ChatHistoryMessage],
    ) -> list[ChatHistoryMessage]:
        self._ensure_table()
        with Session(self._database_repository.engine) as db_session:
            for item in messages:
                db_session.add(
                    ChatHistoryMessageRecord(
                        workflow_id=workflow_id,
                        execution_session_id=execution_session_id,
                        node_id=node_id,
                        role=item.role,
                        content=item.content,
                        created_at=_as_utc(item.timestamp),
                    )
                )
            db_session.commit()
        return self.get_messages(workflow_id, execution_session_id, node_id)

    # -------------------------------------------------------------------------
    def clear_session(self, workflow_id: str, execution_session_id: str) -> None:
        self._ensure_table()
        with Session(self._database_repository.engine) as db_session:
            db_session.execute(
                delete(ChatHistoryMessageRecord).where(
                    ChatHistoryMessageRecord.workflow_id == workflow_id,
                    ChatHistoryMessageRecord.execution_session_id
                    == execution_session_id,
                )
            )
            db_session.commit()

    # -------------------------------------------------------------------------
    def set_messages(
        self,
        workflow_id: str,
        execution_session_id: str,
        node_id: str,
        messages: list[ChatHistoryMessage],
    ) -> None:
        self._ensure_table()
        with Session(self._database_repository.engine) as db_session:
            db_session.execute(
                delete(ChatHistoryMessageRecord).where(
                    ChatHistoryMessageRecord.workflow_id == workflow_id,
                    ChatHistoryMessageRecord.execution_session_id
                    == execution_session_id,
                    ChatHistoryMessageRecord.node_id == node_id,
                )
            )
            for item in messages:
                db_session.add(
                    ChatHistoryMessageRecord(
                        workflow_id=workflow_id,
                        execution_session_id=execution_session_id,
                        node_id=node_id,
                        role=item.role,
                        content=item.content,
                        created_at=_as_utc(item.timestamp),
                    )
                )
            db_session.commit()

    # -------------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        try:
            self._ensure_table()
            with Session(self._database_repository.engine) as db_session:
                db_session.execute(delete(ChatHistoryMessageRecord))
                db_session.commit()
        except OperationalError:
            return


database_chat_history_repository = DatabaseChatHistoryRepository()
