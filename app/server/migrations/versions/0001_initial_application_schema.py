"""Create the initial internal application schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


###############################################################################
def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("session_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_name", sa.String(), nullable=False),
        sa.Column(
            "ollama_base_url",
            sa.String(),
            nullable=False,
        ),
        sa.Column("ollama_chat_model", sa.String(), nullable=False),
        sa.Column("ollama_embedding_model", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("session_name"),
    )
    op.create_table(
        "nodes",
        sa.Column(
            "node_configuration_id", sa.Integer(), autoincrement=True, nullable=False
        ),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("node_key", sa.String(), nullable=False),
        sa.Column("node_type", sa.String(), nullable=False),
        sa.Column("node_version", sa.Integer(), nullable=False),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["user_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("node_configuration_id"),
        sa.UniqueConstraint("session_id", "node_key", name="uq_nodes_session_node_key"),
    )
    op.create_index("ix_nodes_session_id", "nodes", ["session_id"], unique=False)
    op.create_index(
        "ix_nodes_session_type", "nodes", ["session_id", "node_type"], unique=False
    )

    op.create_table(
        "configuration_profiles",
        sa.Column(
            "configuration_profile_id", sa.Integer(), autoincrement=True, nullable=False
        ),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("profile_name", sa.String(), nullable=False),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["user_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("configuration_profile_id"),
        sa.UniqueConstraint(
            "session_id",
            "profile_name",
            name="uq_configuration_profiles_session_name",
        ),
    )
    op.create_index(
        "ix_configuration_profiles_session_id",
        "configuration_profiles",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_configuration_profiles_session_name",
        "configuration_profiles",
        ["session_id", "profile_name"],
        unique=False,
    )

    op.create_table(
        "access_keys",
        sa.Column("access_key_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("api_key", sa.String(), nullable=True),
        sa.Column("base_url", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["user_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("access_key_id"),
        sa.UniqueConstraint(
            "session_id", "provider", name="uq_access_keys_session_provider"
        ),
    )
    op.create_index(
        "ix_access_keys_session_id", "access_keys", ["session_id"], unique=False
    )
    op.create_index(
        "ix_access_keys_provider", "access_keys", ["provider"], unique=False
    )

    op.create_table(
        "chat_history_messages",
        sa.Column(
            "chat_history_message_id", sa.Integer(), autoincrement=True, nullable=False
        ),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("execution_session_id", sa.String(), nullable=False),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("chat_history_message_id"),
    )
    op.create_index(
        "ix_chat_history_lookup",
        "chat_history_messages",
        [
            "workflow_id",
            "execution_session_id",
            "node_id",
            "chat_history_message_id",
        ],
        unique=False,
    )

    op.create_table(
        "execution_runs",
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("workflow_id", sa.String(), nullable=True),
        sa.Column("execution_session_id", sa.String(), nullable=True),
        sa.Column("plan_id", sa.String(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("outputs_json", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("pause_payload_json", sa.JSON(), nullable=True),
        sa.Column("resume_token", sa.String(), nullable=True),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_execution_runs_request_id", "execution_runs", ["request_id"], unique=False
    )
    op.create_index(
        "ix_execution_runs_workflow_id", "execution_runs", ["workflow_id"], unique=False
    )
    op.create_index(
        "ix_execution_runs_status", "execution_runs", ["status"], unique=False
    )

    op.create_table(
        "execution_steps",
        sa.Column(
            "execution_step_id", sa.Integer(), autoincrement=True, nullable=False
        ),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("step_id", sa.String(), nullable=False),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("node_type", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("blocked_reason", sa.String(), nullable=True),
        sa.Column("pause_payload_json", sa.JSON(), nullable=True),
        sa.Column("resume_token", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"], ["execution_runs.run_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("execution_step_id"),
        sa.UniqueConstraint("run_id", "step_id", name="uq_execution_steps_run_step"),
    )
    op.create_index(
        "ix_execution_steps_run_id", "execution_steps", ["run_id"], unique=False
    )

    op.create_table(
        "execution_events",
        sa.Column(
            "execution_event_id", sa.Integer(), autoincrement=True, nullable=False
        ),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("step_id", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["execution_runs.run_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("execution_event_id"),
        sa.UniqueConstraint(
            "run_id", "sequence", name="uq_execution_events_run_sequence"
        ),
    )
    op.create_index(
        "ix_execution_events_run_id", "execution_events", ["run_id"], unique=False
    )


###############################################################################
def downgrade() -> None:
    op.drop_index("ix_execution_events_run_id", table_name="execution_events")
    op.drop_table("execution_events")
    op.drop_index("ix_execution_steps_run_id", table_name="execution_steps")
    op.drop_table("execution_steps")
    op.drop_index("ix_execution_runs_status", table_name="execution_runs")
    op.drop_index("ix_execution_runs_workflow_id", table_name="execution_runs")
    op.drop_index("ix_execution_runs_request_id", table_name="execution_runs")
    op.drop_table("execution_runs")
    op.drop_index("ix_chat_history_lookup", table_name="chat_history_messages")
    op.drop_table("chat_history_messages")
    op.drop_index("ix_access_keys_provider", table_name="access_keys")
    op.drop_index("ix_access_keys_session_id", table_name="access_keys")
    op.drop_table("access_keys")
    op.drop_index(
        "ix_configuration_profiles_session_name", table_name="configuration_profiles"
    )
    op.drop_index(
        "ix_configuration_profiles_session_id", table_name="configuration_profiles"
    )
    op.drop_table("configuration_profiles")
    op.drop_index("ix_nodes_session_type", table_name="nodes")
    op.drop_index("ix_nodes_session_id", table_name="nodes")
    op.drop_table("nodes")
    op.drop_table("user_sessions")
