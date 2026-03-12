from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

from ParaGraph.server.repositories.schemas.types import JSONSequence

Base = declarative_base()


###############################################################################
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


###############################################################################
class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id = Column(Integer, primary_key=True, autoincrement=True)
    session_name = Column(String(120), nullable=False, unique=True)
    ollama_base_url = Column(String(512), nullable=False, default="http://127.0.0.1:11434")
    ollama_chat_model = Column(String(255), nullable=False, default="llama3.2")
    ollama_embedding_model = Column(String(255), nullable=False, default="nomic-embed-text")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    nodes = relationship(
        "NodeConfiguration",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    access_keys = relationship(
        "AccessKey",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    configuration_profiles = relationship(
        "ConfigurationProfile",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


###############################################################################
class NodeConfiguration(Base):
    __tablename__ = "nodes"

    node_configuration_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("user_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    node_key = Column(String(255), nullable=False)
    node_type = Column(String(120), nullable=False)
    node_version = Column(Integer, nullable=False)
    configuration_json = Column(JSONSequence, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    session = relationship("UserSession", back_populates="nodes")

    __table_args__ = (
        UniqueConstraint("session_id", "node_key", name="uq_nodes_session_node_key"),
        Index("ix_nodes_session_type", "session_id", "node_type"),
    )



###############################################################################
class ConfigurationProfile(Base):
    __tablename__ = "configuration_profiles"

    configuration_profile_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("user_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    profile_name = Column(String(120), nullable=False)
    configuration_json = Column(JSONSequence, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    session = relationship("UserSession", back_populates="configuration_profiles")

    __table_args__ = (
        UniqueConstraint("session_id", "profile_name", name="uq_configuration_profiles_session_name"),
        Index("ix_configuration_profiles_session_name", "session_id", "profile_name"),
    )

###############################################################################
class AccessKey(Base):
    __tablename__ = "access_keys"

    access_key_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("user_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    api_key = Column(String(1024), nullable=True)
    base_url = Column(String(512), nullable=True)
    metadata_json = Column(JSONSequence, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    session = relationship("UserSession", back_populates="access_keys")

    __table_args__ = (
        UniqueConstraint("session_id", "provider", name="uq_access_keys_session_provider"),
        Index("ix_access_keys_provider", "provider"),
    )
