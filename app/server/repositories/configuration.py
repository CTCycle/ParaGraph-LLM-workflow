from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.configurations.startup import get_server_settings
from server.contracts.configuration import (
    DEFAULT_SESSION_NAME,
    PROFILE_NAME_PATTERN,
)
from server.repositories.database.sqlite import SQLiteRepository
from server.repositories.schemas import (
    ConfigurationProfile,
    ProviderConfiguration,
    UserSession,
)


###############################################################################
class ConfigurationRepository:
    # -------------------------------------------------------------------------
    def __init__(self, database_repository: SQLiteRepository | None = None) -> None:
        self._database_repository = database_repository

    # -------------------------------------------------------------------------
    def _database_engine(self):
        if self._database_repository is not None:
            return self._database_repository.engine
        return SQLiteRepository(get_server_settings().database).engine

    # -------------------------------------------------------------------------
    def _normalize_session_name(self, session_name: str | None) -> str:
        normalized = (session_name or "").strip()
        return normalized or DEFAULT_SESSION_NAME

    # -------------------------------------------------------------------------
    def _normalize_profile_name(self, profile_name: str) -> str:
        normalized = profile_name.strip()
        if not normalized:
            raise ValueError("Profile name is required")
        if not re.fullmatch(PROFILE_NAME_PATTERN, normalized):
            raise ValueError(
                "Profile name may include only letters, numbers, spaces, dot, underscore, and dash"
            )
        return normalized

    # -------------------------------------------------------------------------
    def _format_timestamp(self, value: datetime | None) -> str:
        timestamp = value or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc).isoformat()

    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    @staticmethod
    def _get_session(db_session: Session, session_name: str) -> UserSession | None:
        return db_session.execute(
            select(UserSession).where(UserSession.session_name == session_name)
        ).scalar_one_or_none()

    # -------------------------------------------------------------------------
    def _serialize_configuration(
        self,
        session_row: UserSession,
        provider_rows: list[ProviderConfiguration],
    ) -> dict[str, Any]:
        return {
            "session_name": session_row.session_name,
            "provider_configurations": [
                {
                    "provider": row.provider,
                    "api_key": row.api_key,
                    "base_url": row.base_url,
                    "metadata": row.metadata_json or {},
                }
                for row in provider_rows
            ],
        }

    # -------------------------------------------------------------------------
    @staticmethod
    def _load_provider_configurations(
        db_session: Session, session_id: int
    ) -> list[ProviderConfiguration]:
        return list(
            db_session.execute(
                select(ProviderConfiguration)
                .where(ProviderConfiguration.session_id == session_id)
                .order_by(ProviderConfiguration.provider.asc())
            ).scalars()
        )

    # -------------------------------------------------------------------------
    def _serialize_profile_summary(
        self, profile_row: ConfigurationProfile
    ) -> dict[str, str]:
        return {
            "profile_name": profile_row.profile_name,
            "created_at": self._format_timestamp(profile_row.created_at),
            "updated_at": self._format_timestamp(profile_row.updated_at),
        }

    # -------------------------------------------------------------------------
    def load_configuration(self, session_name: str | None = None) -> dict[str, Any]:
        normalized_session_name = self._normalize_session_name(session_name)
        with Session(self._database_engine()) as db_session:
            session_row, created = self._get_or_create_session(
                db_session, normalized_session_name
            )
            if created:
                db_session.commit()
                db_session.refresh(session_row)
            provider_rows = self._load_provider_configurations(
                db_session, session_row.session_id
            )
            return self._serialize_configuration(session_row, provider_rows)

    # -------------------------------------------------------------------------
    def save_configuration(
        self,
        *,
        session_name: str | None,
        provider_configurations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        normalized_session_name = self._normalize_session_name(session_name)

        provider_map: dict[str, dict[str, Any]] = {}
        for item in provider_configurations:
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

        with Session(self._database_engine()) as db_session:
            session_row, _ = self._get_or_create_session(
                db_session, normalized_session_name
            )
            for row in list(session_row.provider_configurations):
                db_session.delete(row)

            for payload in provider_map.values():
                has_value = bool(
                    payload["api_key"] or payload["base_url"] or payload["metadata"]
                )
                if not has_value:
                    continue
                db_session.add(
                    ProviderConfiguration(
                        session_id=session_row.session_id,
                        provider=payload["provider"],
                        api_key=payload["api_key"],
                        base_url=payload["base_url"],
                        metadata_json=payload["metadata"],
                    )
                )

            db_session.commit()
            db_session.refresh(session_row)
            provider_rows = self._load_provider_configurations(
                db_session, session_row.session_id
            )
            return self._serialize_configuration(session_row, provider_rows)

    # -------------------------------------------------------------------------
    def list_configuration_profiles(
        self, session_name: str | None = None
    ) -> dict[str, Any]:
        normalized_session_name = self._normalize_session_name(session_name)
        with Session(self._database_engine()) as db_session:
            session_row = self._get_session(db_session, normalized_session_name)
            if session_row is None:
                return {"session_name": normalized_session_name, "profiles": []}

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

    # -------------------------------------------------------------------------
    def load_configuration_profile(
        self, *, session_name: str | None, profile_name: str
    ) -> dict[str, Any]:
        normalized_session_name = self._normalize_session_name(session_name)
        normalized_profile_name = self._normalize_profile_name(profile_name)

        with Session(self._database_engine()) as db_session:
            session_row = self._get_session(db_session, normalized_session_name)
            if session_row is None:
                raise KeyError(
                    f"Configuration profile '{normalized_profile_name}' was not found"
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
            provider_configurations = payload.get("provider_configurations")
            if not isinstance(provider_configurations, list):
                raise ValueError(
                    f"Configuration profile '{normalized_profile_name}' is invalid"
                )

            return {
                "session_name": normalized_session_name,
                "provider_configurations": provider_configurations,
            }

    # -------------------------------------------------------------------------
    def save_configuration_profile(
        self,
        *,
        session_name: str | None,
        profile_name: str,
        configuration_json: dict[str, Any],
    ) -> None:
        normalized_session_name = self._normalize_session_name(session_name)
        normalized_profile_name = self._normalize_profile_name(profile_name)

        with Session(self._database_engine()) as db_session:
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


configuration_repository = ConfigurationRepository()
