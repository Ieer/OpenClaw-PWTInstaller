"""add transactional event outbox"""

from alembic import op
import sqlalchemy as sa


revision = "20261114_0014"
down_revision = "20260524_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_outbox",
        sa.Column("event_id", sa.Uuid, primary_key=True),
        sa.Column("event", sa.JSON, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_event_outbox_pending", "event_outbox", ["next_attempt_at"], postgresql_where=sa.text("delivered_at IS NULL"))
    op.create_index("idx_event_outbox_delivered", "event_outbox", ["delivered_at"], postgresql_where=sa.text("delivered_at IS NOT NULL"))


def downgrade() -> None:
    op.drop_table("event_outbox")