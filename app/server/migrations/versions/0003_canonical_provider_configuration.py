"""Consolidate provider configuration into one canonical table and payload."""

from __future__ import annotations

import json
from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_canonical_provider_configuration"
down_revision: Union[str, None] = "0002_remove_node_configuration_mirror"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


###############################################################################
def _json_object(value: Any, description: str) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid {description} JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Invalid {description}: expected an object")
    return value


###############################################################################
def _canonical_profile_payload(value: Any, profile_name: str) -> dict[str, Any]:
    payload = _json_object(value, f"configuration profile '{profile_name}'")
    if "provider_configurations" in payload:
        if "access_keys" in payload or "ollama" in payload:
            raise RuntimeError(
                f"Configuration profile '{profile_name}' mixes canonical and legacy fields"
            )
        providers = payload["provider_configurations"]
        if not isinstance(providers, list):
            raise RuntimeError(
                f"Configuration profile '{profile_name}' has invalid provider_configurations"
            )
        return {
            "session_name": payload.get("session_name", "default"),
            "provider_configurations": providers,
        }

    access_keys = payload.get("access_keys")
    ollama = payload.get("ollama")
    if not isinstance(access_keys, list) or not isinstance(ollama, dict):
        raise RuntimeError(
            f"Configuration profile '{profile_name}' is not a recognized configuration shape"
        )

    providers = list(access_keys)
    ollama_metadata = {
        key: ollama[key]
        for key in ("chat_model", "embedding_model")
        if key in ollama
    }
    if ollama.get("base_url") or ollama_metadata:
        providers.append(
            {
                "provider": "ollama",
                "api_key": None,
                "base_url": ollama.get("base_url"),
                "metadata": ollama_metadata,
            }
        )
    return {
        "session_name": payload.get("session_name", "default"),
        "provider_configurations": providers,
    }


###############################################################################
def _migrate_profiles(connection: sa.Connection) -> None:
    rows = connection.execute(
        sa.text(
            "SELECT configuration_profile_id, profile_name, configuration_json "
            "FROM configuration_profiles"
        )
    ).mappings()
    for row in rows:
        payload = _canonical_profile_payload(
            row["configuration_json"], str(row["profile_name"])
        )
        connection.execute(
            sa.text(
                "UPDATE configuration_profiles "
                "SET configuration_json = :configuration_json "
                "WHERE configuration_profile_id = :profile_id"
            ),
            {
                "configuration_json": json.dumps(
                    payload, separators=(",", ":"), ensure_ascii=True
                ),
                "profile_id": row["configuration_profile_id"],
            },
        )


###############################################################################
def _migrate_ollama_configurations(connection: sa.Connection) -> None:
    sessions = connection.execute(
        sa.text(
            "SELECT session_id, ollama_base_url, ollama_chat_model, "
            "ollama_embedding_model FROM user_sessions"
        )
    ).mappings()
    for session in sessions:
        existing = connection.execute(
            sa.text(
                "SELECT provider_configuration_id, api_key, base_url, metadata_json "
                "FROM provider_configurations "
                "WHERE session_id = :session_id AND provider = 'ollama'"
            ),
            {"session_id": session["session_id"]},
        ).mappings().first()
        if existing is None:
            connection.execute(
                sa.text(
                    "INSERT INTO provider_configurations "
                    "(session_id, provider, api_key, base_url, metadata_json, created_at, updated_at) "
                    "VALUES (:session_id, 'ollama', NULL, :base_url, :metadata_json, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "session_id": session["session_id"],
                    "base_url": session["ollama_base_url"],
                    "metadata_json": json.dumps(
                        {
                            "chat_model": session["ollama_chat_model"],
                            "embedding_model": session["ollama_embedding_model"],
                        },
                        separators=(",", ":"),
                    ),
                },
            )
            continue

        metadata = _json_object(existing["metadata_json"], "Ollama provider metadata")
        metadata.setdefault("chat_model", session["ollama_chat_model"])
        metadata.setdefault("embedding_model", session["ollama_embedding_model"])
        connection.execute(
            sa.text(
                "UPDATE provider_configurations SET base_url = :base_url, "
                "metadata_json = :metadata_json "
                "WHERE provider_configuration_id = :provider_configuration_id"
            ),
            {
                "base_url": existing["base_url"] or session["ollama_base_url"],
                "metadata_json": json.dumps(
                    metadata, separators=(",", ":"), ensure_ascii=True
                ),
                "provider_configuration_id": existing["provider_configuration_id"],
            },
        )


###############################################################################
def _rename_provider_indexes_to_canonical() -> None:
    op.drop_index(
        "ix_access_keys_session_id", table_name="provider_configurations"
    )
    op.drop_index("ix_access_keys_provider", table_name="provider_configurations")
    op.create_index(
        "ix_provider_configurations_session_id",
        "provider_configurations",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_configurations_provider",
        "provider_configurations",
        ["provider"],
        unique=False,
    )


###############################################################################
def _preserve_dependent_rows(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            "CREATE TEMP TABLE _provider_configurations_backup AS "
            "SELECT * FROM provider_configurations"
        )
    )
    connection.execute(
        sa.text(
            "CREATE TEMP TABLE _configuration_profiles_backup AS "
            "SELECT * FROM configuration_profiles"
        )
    )


###############################################################################
def _restore_dependent_rows(connection: sa.Connection) -> None:
    connection.execute(sa.text("DELETE FROM provider_configurations"))
    connection.execute(
        sa.text(
            "INSERT INTO provider_configurations "
            "SELECT * FROM _provider_configurations_backup"
        )
    )
    connection.execute(sa.text("DELETE FROM configuration_profiles"))
    connection.execute(
        sa.text(
            "INSERT INTO configuration_profiles "
            "SELECT * FROM _configuration_profiles_backup"
        )
    )


###############################################################################
def upgrade() -> None:
    connection = op.get_bind()
    _migrate_profiles(connection)
    op.rename_table("access_keys", "provider_configurations")
    with op.batch_alter_table(
        "provider_configurations", recreate="always"
    ) as batch_op:
        batch_op.alter_column(
            "access_key_id", new_column_name="provider_configuration_id"
        )
        batch_op.drop_constraint("uq_access_keys_session_provider", type_="unique")
        batch_op.create_unique_constraint(
            "uq_provider_configurations_session_provider", ["session_id", "provider"]
        )
    _rename_provider_indexes_to_canonical()
    _migrate_ollama_configurations(connection)
    _preserve_dependent_rows(connection)
    with op.batch_alter_table("user_sessions", recreate="always") as batch_op:
        batch_op.drop_column("ollama_base_url")
        batch_op.drop_column("ollama_chat_model")
        batch_op.drop_column("ollama_embedding_model")
    _restore_dependent_rows(connection)


###############################################################################
def _restore_legacy_profile_payload(value: Any, profile_name: str) -> dict[str, Any]:
    payload = _json_object(value, f"configuration profile '{profile_name}'")
    providers = payload.get("provider_configurations")
    if not isinstance(providers, list):
        raise RuntimeError(f"Configuration profile '{profile_name}' is invalid")
    ollama: dict[str, Any] = {}
    access_keys: list[Any] = []
    for item in providers:
        if not isinstance(item, dict):
            raise RuntimeError(f"Configuration profile '{profile_name}' is invalid")
        if item.get("provider") == "ollama":
            metadata = item.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            ollama = {
                "base_url": item.get("base_url"),
                "chat_model": metadata.get("chat_model", "llama3.2"),
                "embedding_model": metadata.get(
                    "embedding_model", "nomic-embed-text"
                ),
            }
        else:
            access_keys.append(item)
    return {
        "session_name": payload.get("session_name", "default"),
        "access_keys": access_keys,
        "ollama": ollama,
    }


###############################################################################
def downgrade() -> None:
    connection = op.get_bind()
    sessions: dict[int, dict[str, Any]] = {}
    for row in connection.execute(
        sa.text(
            "SELECT session_id, base_url, metadata_json FROM provider_configurations "
            "WHERE provider = 'ollama'"
        )
    ).mappings():
        metadata = _json_object(row["metadata_json"], "Ollama provider metadata")
        sessions[int(row["session_id"])] = {
            "base_url": row["base_url"] or "http://127.0.0.1:11434",
            "chat_model": metadata.get("chat_model", "llama3.2"),
            "embedding_model": metadata.get("embedding_model", "nomic-embed-text"),
        }

    profile_rows = connection.execute(
        sa.text(
            "SELECT configuration_profile_id, profile_name, configuration_json "
            "FROM configuration_profiles"
        )
    ).mappings()
    for row in profile_rows:
        payload = _restore_legacy_profile_payload(
            row["configuration_json"], str(row["profile_name"])
        )
        connection.execute(
            sa.text(
                "UPDATE configuration_profiles SET configuration_json = :payload "
                "WHERE configuration_profile_id = :profile_id"
            ),
            {
                "payload": json.dumps(payload, separators=(",", ":")),
                "profile_id": row["configuration_profile_id"],
            },
        )

    with op.batch_alter_table("user_sessions", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "ollama_base_url",
                sa.String(),
                nullable=False,
                server_default="http://127.0.0.1:11434",
            )
        )
        batch_op.add_column(
            sa.Column(
                "ollama_chat_model",
                sa.String(),
                nullable=False,
                server_default="llama3.2",
            )
        )
        batch_op.add_column(
            sa.Column(
                "ollama_embedding_model",
                sa.String(),
                nullable=False,
                server_default="nomic-embed-text",
            )
        )
    for session_id, payload in sessions.items():
        connection.execute(
            sa.text(
                "UPDATE user_sessions SET ollama_base_url = :base_url, "
                "ollama_chat_model = :chat_model, "
                "ollama_embedding_model = :embedding_model "
                "WHERE session_id = :session_id"
            ),
            {"session_id": session_id, **payload},
        )

    connection.execute(sa.text("DELETE FROM provider_configurations WHERE provider = 'ollama'"))
    op.rename_table("provider_configurations", "access_keys")
    with op.batch_alter_table("access_keys", recreate="always") as batch_op:
        batch_op.alter_column(
            "provider_configuration_id", new_column_name="access_key_id"
        )
        batch_op.drop_constraint(
            "uq_provider_configurations_session_provider", type_="unique"
        )
        batch_op.create_unique_constraint(
            "uq_access_keys_session_provider", ["session_id", "provider"]
        )
    op.drop_index(
        "ix_provider_configurations_session_id", table_name="access_keys"
    )
    op.drop_index("ix_provider_configurations_provider", table_name="access_keys")
    op.create_index("ix_access_keys_session_id", "access_keys", ["session_id"])
    op.create_index("ix_access_keys_provider", "access_keys", ["provider"])
