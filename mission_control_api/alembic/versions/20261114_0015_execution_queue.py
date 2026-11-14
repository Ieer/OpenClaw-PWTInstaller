"""add managed execution leases and provider budgets"""

from alembic import op
import sqlalchemy as sa


revision = "20261114_0015"
down_revision = "20261114_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_jobs",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("agent_slug", sa.Text, nullable=False),
        sa.Column("idempotency_key", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("provider", sa.Text),
        sa.Column("estimated_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("payload_hash", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="QUEUED"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="900"),
        sa.Column("worker_id", sa.Text),
        sa.Column("lease_token", sa.Uuid),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("deadline_at", sa.DateTime(timezone=True)),
        sa.Column("result", sa.JSON),
        sa.Column("last_error", sa.Text),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("agent_slug", "idempotency_key", name="uq_execution_job_idempotency"),
    )
    op.create_index("idx_execution_jobs_ready", "execution_jobs", ["agent_slug", "kind", "priority", "created_at"], postgresql_where=sa.text("status = 'QUEUED'"))
    op.create_index("idx_execution_jobs_running", "execution_jobs", ["lease_expires_at"], postgresql_where=sa.text("status = 'RUNNING'"))
    op.create_table(
        "execution_provider_charges",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("tokens", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_execution_provider_charges_window", "execution_provider_charges", ["provider", "created_at"])


def downgrade() -> None:
    op.drop_table("execution_provider_charges")
    op.drop_table("execution_jobs")