"""Store non-database runtime settings in each application database."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_database_backed_application_settings"
down_revision: Union[str, None] = "0003_canonical_provider_configuration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


###############################################################################
def upgrade() -> None:
    op.create_table(
        "application_settings",
        sa.Column("settings_id", sa.Integer(), nullable=False),
        sa.Column("global_seed", sa.Integer(), nullable=False, server_default="42"),
        sa.Column("jobs_polling_interval", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("jobs_retention_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("legacy_imported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("settings_id"),
        sa.CheckConstraint("settings_id = 1", name="ck_application_settings_singleton"),
        sa.CheckConstraint(
            "jobs_polling_interval > 0",
            name="ck_application_settings_polling_interval_positive",
        ),
        sa.CheckConstraint(
            "jobs_retention_days >= 1",
            name="ck_application_settings_retention_days_positive",
        ),
    )


###############################################################################
def downgrade() -> None:
    op.drop_table("application_settings")
