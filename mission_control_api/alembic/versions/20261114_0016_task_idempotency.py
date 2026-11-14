"""add transactional task action idempotency"""

from alembic import op
import sqlalchemy as sa


revision = "20261114_0016"
down_revision = "20261114_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_action_requests",
        sa.Column("scope", sa.Text, primary_key=True),
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("request_hash", sa.Text, nullable=False),
        sa.Column("response", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("task_action_requests")