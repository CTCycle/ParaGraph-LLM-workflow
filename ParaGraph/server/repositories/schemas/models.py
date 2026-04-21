from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ParaGraph.server.repositories.schemas.types import JSONSequence

###############################################################################
class Base(DeclarativeBase):
    pass


###############################################################################
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


###############################################################################
class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_name: Mapped[str] = mapped_column(nullable=False, unique=True)
    ollama_base_url: Mapped[str] = mapped_column(
        nullable=False, default="http://127.0.0.1:11434"
    )
    ollama_chat_model: Mapped[str] = mapped_column(nullable=False, default="llama3.2")
    ollama_embedding_model: Mapped[str] = mapped_column(
        nullable=False, default="nomic-embed-text"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    nodes: Mapped[list[NodeConfiguration]] = relationship(
        "NodeConfiguration",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    access_keys: Mapped[list[AccessKey]] = relationship(
        "AccessKey",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    configuration_profiles: Mapped[list[ConfigurationProfile]] = relationship(
        "ConfigurationProfile",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


###############################################################################
class NodeConfiguration(Base):
    __tablename__ = "nodes"

    node_configuration_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("user_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_key: Mapped[str] = mapped_column(nullable=False)
    node_type: Mapped[str] = mapped_column(nullable=False)
    node_version: Mapped[int] = mapped_column(nullable=False)
    configuration_json: Mapped[Any] = mapped_column(JSONSequence, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    session: Mapped[UserSession] = relationship("UserSession", back_populates="nodes")

    __table_args__ = (
        UniqueConstraint("session_id", "node_key", name="uq_nodes_session_node_key"),
        Index("ix_nodes_session_type", "session_id", "node_type"),
    )


###############################################################################
class ConfigurationProfile(Base):
    __tablename__ = "configuration_profiles"

    configuration_profile_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("user_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_name: Mapped[str] = mapped_column(nullable=False)
    configuration_json: Mapped[Any] = mapped_column(JSONSequence, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    session: Mapped[UserSession] = relationship(
        "UserSession", back_populates="configuration_profiles"
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id", "profile_name", name="uq_configuration_profiles_session_name"
        ),
        Index("ix_configuration_profiles_session_name", "session_id", "profile_name"),
    )


###############################################################################
class AccessKey(Base):
    __tablename__ = "access_keys"

    access_key_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("user_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(nullable=False)
    api_key: Mapped[str | None] = mapped_column(nullable=True)
    base_url: Mapped[str | None] = mapped_column(nullable=True)
    metadata_json: Mapped[Any] = mapped_column(
        JSONSequence, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    session: Mapped[UserSession] = relationship(
        "UserSession", back_populates="access_keys"
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id", "provider", name="uq_access_keys_session_provider"
        ),
        Index("ix_access_keys_provider", "provider"),
    )


###############################################################################
class ChatHistoryMessageRecord(Base):
    __tablename__ = "chat_history_messages"

    chat_history_message_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True
    )
    workflow_id: Mapped[str] = mapped_column(nullable=False)
    execution_session_id: Mapped[str] = mapped_column(nullable=False)
    node_id: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        Index(
            "ix_chat_history_lookup",
            "workflow_id",
            "execution_session_id",
            "node_id",
            "chat_history_message_id",
        ),
    )
