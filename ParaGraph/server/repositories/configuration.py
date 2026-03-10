from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ParaGraph.server.entities.configuration import DEFAULT_SESSION_NAME
from ParaGraph.server.repositories.database import database
from ParaGraph.server.repositories.schemas import AccessKey, NodeConfiguration, UserSession


###############################################################################
class ConfigurationRepository:
    def _normalize_session_name(self, session_name: str | None) -> str:
        normalized = (session_name or "").strip()
        return normalized or DEFAULT_SESSION_NAME

    def _get_or_create_session(self, db_session: Session, session_name: str) -> tuple[UserSession, bool]:
        existing = db_session.execute(
            select(UserSession).where(UserSession.session_name == session_name)
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False

        created = UserSession(session_name=session_name)
        db_session.add(created)
        db_session.flush()
        return created, True

    def _serialize_configuration(self, session_row: UserSession, access_rows: list[AccessKey]) -> dict[str, Any]:
        return {
            "session_name": session_row.session_name,
            "access_keys": [
                {
                    "provider": row.provider,
                    "api_key": row.api_key,
                    "base_url": row.base_url,
                    "metadata": row.metadata_json or {},
                }
                for row in access_rows
            ],
            "ollama": {
                "base_url": session_row.ollama_base_url,
                "chat_model": session_row.ollama_chat_model,
                "embedding_model": session_row.ollama_embedding_model,
            },
        }

    def _load_access_keys(self, db_session: Session, session_id: int) -> list[AccessKey]:
        return list(
            db_session.execute(
                select(AccessKey)
                .where(AccessKey.session_id == session_id)
                .order_by(AccessKey.provider.asc())
            ).scalars()
        )

    def load_configuration(self, session_name: str | None = None) -> dict[str, Any]:
        normalized_session_name = self._normalize_session_name(session_name)
        with Session(database.backend.engine) as db_session:
            session_row, created = self._get_or_create_session(db_session, normalized_session_name)
            if created:
                db_session.commit()
                db_session.refresh(session_row)
            access_rows = self._load_access_keys(db_session, session_row.session_id)
            return self._serialize_configuration(session_row, access_rows)

    def save_configuration(
        self,
        *,
        session_name: str | None,
        access_keys: list[dict[str, Any]],
        ollama: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_session_name = self._normalize_session_name(session_name)

        provider_map: dict[str, dict[str, Any]] = {}
        for item in access_keys:
            provider = str(item.get("provider") or "").strip().lower()
            if not provider:
                continue
            provider_map[provider] = {
                "provider": provider,
                "api_key": item.get("api_key"),
                "base_url": item.get("base_url"),
                "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            }

        with Session(database.backend.engine) as db_session:
            session_row, _ = self._get_or_create_session(db_session, normalized_session_name)
            session_row.ollama_base_url = str(ollama.get("base_url") or session_row.ollama_base_url)
            session_row.ollama_chat_model = str(ollama.get("chat_model") or session_row.ollama_chat_model)
            session_row.ollama_embedding_model = str(ollama.get("embedding_model") or session_row.ollama_embedding_model)

            db_session.execute(delete(AccessKey).where(AccessKey.session_id == session_row.session_id))

            for payload in provider_map.values():
                has_value = bool(payload["api_key"] or payload["base_url"] or payload["metadata"])
                if not has_value:
                    continue
                db_session.add(
                    AccessKey(
                        session_id=session_row.session_id,
                        provider=payload["provider"],
                        api_key=payload["api_key"],
                        base_url=payload["base_url"],
                        metadata_json=payload["metadata"],
                    )
                )

            db_session.commit()
            db_session.refresh(session_row)
            access_rows = self._load_access_keys(db_session, session_row.session_id)
            return self._serialize_configuration(session_row, access_rows)

    def save_node_configuration(
        self,
        *,
        node_key: str,
        node_type: str,
        node_version: int,
        configuration_json: dict[str, Any],
        session_name: str | None = None,
    ) -> None:
        normalized_session_name = self._normalize_session_name(session_name)
        with Session(database.backend.engine) as db_session:
            session_row, _ = self._get_or_create_session(db_session, normalized_session_name)
            existing = db_session.execute(
                select(NodeConfiguration).where(
                    NodeConfiguration.session_id == session_row.session_id,
                    NodeConfiguration.node_key == node_key,
                )
            ).scalar_one_or_none()
            if existing is None:
                db_session.add(
                    NodeConfiguration(
                        session_id=session_row.session_id,
                        node_key=node_key,
                        node_type=node_type,
                        node_version=node_version,
                        configuration_json=configuration_json,
                    )
                )
            else:
                existing.node_type = node_type
                existing.node_version = node_version
                existing.configuration_json = configuration_json

            db_session.commit()


configuration_repository = ConfigurationRepository()
