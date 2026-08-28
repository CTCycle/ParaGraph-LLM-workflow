"""Remove the unused database mirror of node manifests.

Revision ID: 0002_remove_node_configuration_mirror
Revises: 0001_initial
Create Date: 2026-08-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_remove_node_configuration_mirror"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

###############################################################################
def upgrade() -> None:
    op.drop_index("ix_nodes_session_type", table_name="nodes")
    op.drop_index("ix_nodes_session_id", table_name="nodes")
    op.drop_table("nodes")

###############################################################################
def downgrade() -> None:
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
