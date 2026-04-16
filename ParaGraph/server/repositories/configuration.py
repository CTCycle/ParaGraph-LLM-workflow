from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ParaGraph.server.domain.configuration import DEFAULT_SESSION_NAME
from ParaGraph.server.repositories.database import database
from ParaGraph.server.repositories.schemas import (
    AccessKey,
    ConfigurationProfile,
    NodeConfiguration,
    UserSession,
)


###############################################################################
class ConfigurationRepository:
    _profile_name_pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,119}$")

    def _normalize_session_name(self, session_name: str | None) -> str:
        normalized = (session_name or "").strip()
        return normalized or DEFAULT_SESSION_NAME

    def _normalize_profile_name(self, profile_name: str) -> str:
        normalized = profile_name.strip()
        if not normalized:
            raise ValueError("Profile name is required")
        if not self._profile_name_pattern.fullmatch(normalized):
            raise ValueError(
                "Profile name may include only letters, numbers, spaces, dot, underscore, and dash"
            )
        return normalized

    def _format_timestamp(self, value: datetime | None) -> str:
        timestamp = value or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc).isoformat()

    def _get_or_create_session(
        self, db_session: Session, session_name: str
    ) -> tuple[UserSession, bool]:
        existing = db_session.execute(
            select(UserSession).where(UserSession.session_name == session_name)
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False

        created = UserSession(session_name=session_name)
        db_session.add(created)
        db_session.flush()
        return created, True

    def _serialize_configuration(
        self, session_row: UserSession, access_rows: list[AccessKey]
    ) -> dict[str, Any]:
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

    def _load_access_keys(
        self, db_session: Session, session_id: int
    ) -> list[AccessKey]:
        return list(
            db_session.execute(
                select(AccessKey)
                .where(AccessKey.session_id == session_id)
                .order_by(AccessKey.provider.asc())
            ).scalars()
        )

    def _serialize_profile_summary(
        self, profile_row: ConfigurationProfile
    ) -> dict[str, str]:
        return {
            "profile_name": profile_row.profile_name,
            "created_at": self._format_timestamp(profile_row.created_at),
            "updated_at": self._format_timestamp(profile_row.updated_at),
        }

    def load_configuration(self, session_name: str | None = None) -> dict[str, Any]:
        normalized_session_name = self._normalize_session_name(session_name)
        with Session(database.backend.engine) as db_session:
            session_row, created = self._get_or_create_session(
                db_session, normalized_session_name
            )
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
                "metadata": item.get("metadata")
                if isinstance(item.get("metadata"), dict)
                else {},
            }

        with Session(database.backend.engine) as db_session:
            session_row, _ = self._get_or_create_session(
                db_session, normalized_session_name
            )
            session_row.ollama_base_url = str(
                ollama.get("base_url") or session_row.ollama_base_url
            )
            session_row.ollama_chat_model = str(
                ollama.get("chat_model") or session_row.ollama_chat_model
            )
            session_row.ollama_embedding_model = str(
                ollama.get("embedding_model") or session_row.ollama_embedding_model
            )

            db_session.execute(
                delete(AccessKey).where(AccessKey.session_id == session_row.session_id)
            )

            for payload in provider_map.values():
                has_value = bool(
                    payload["api_key"] or payload["base_url"] or payload["metadata"]
                )
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

    def list_configuration_profiles(
        self, session_name: str | None = None
    ) -> dict[str, Any]:
        normalized_session_name = self._normalize_session_name(session_name)
        with Session(database.backend.engine) as db_session:
            session_row, created = self._get_or_create_session(
                db_session, normalized_session_name
            )
            if created:
                db_session.commit()
                db_session.refresh(session_row)

            profile_rows = list(
                db_session.execute(
                    select(ConfigurationProfile)
                    .where(ConfigurationProfile.session_id == session_row.session_id)
                    .order_by(
                        ConfigurationProfile.updated_at.desc(),
                        ConfigurationProfile.profile_name.asc(),
                    )
                ).scalars()
            )
            return {
                "session_name": session_row.session_name,
                "profiles": [
                    self._serialize_profile_summary(row) for row in profile_rows
                ],
            }

    def load_configuration_profile(
        self, *, session_name: str | None, profile_name: str
    ) -> dict[str, Any]:
        normalized_session_name = self._normalize_session_name(session_name)
        normalized_profile_name = self._normalize_profile_name(profile_name)

        with Session(database.backend.engine) as db_session:
            session_row, _ = self._get_or_create_session(
                db_session, normalized_session_name
            )
            profile_row = db_session.execute(
                select(ConfigurationProfile).where(
                    ConfigurationProfile.session_id == session_row.session_id,
                    ConfigurationProfile.profile_name == normalized_profile_name,
                )
            ).scalar_one_or_none()

            if profile_row is None:
                raise KeyError(
                    f"Configuration profile '{normalized_profile_name}' was not found"
                )

            payload = profile_row.configuration_json
            if not isinstance(payload, dict):
                raise ValueError(
                    f"Configuration profile '{normalized_profile_name}' is invalid"
                )

            access_keys = payload.get("access_keys")
            if not isinstance(access_keys, list):
                access_keys = []
            ollama = (
                payload.get("ollama") if isinstance(payload.get("ollama"), dict) else {}
            )

            return {
                "session_name": normalized_session_name,
                "access_keys": access_keys,
                "ollama": ollama,
            }

    def save_configuration_profile(
        self,
        *,
        session_name: str | None,
        profile_name: str,
        configuration_json: dict[str, Any],
    ) -> None:
        normalized_session_name = self._normalize_session_name(session_name)
        normalized_profile_name = self._normalize_profile_name(profile_name)

        with Session(database.backend.engine) as db_session:
            session_row, _ = self._get_or_create_session(
                db_session, normalized_session_name
            )
            existing = db_session.execute(
                select(ConfigurationProfile).where(
                    ConfigurationProfile.session_id == session_row.session_id,
                    ConfigurationProfile.profile_name == normalized_profile_name,
                )
            ).scalar_one_or_none()

            if existing is None:
                db_session.add(
                    ConfigurationProfile(
                        session_id=session_row.session_id,
                        profile_name=normalized_profile_name,
                        configuration_json=configuration_json,
                    )
                )
            else:
                existing.configuration_json = configuration_json

            db_session.commit()

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
            session_row, _ = self._get_or_create_session(
                db_session, normalized_session_name
            )
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
