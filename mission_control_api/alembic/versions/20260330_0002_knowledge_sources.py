"""add knowledge_sources table

Revision ID: 20260330_0002
Revises: 20260318_0001
Create Date: 2026-03-30
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0002"
down_revision: str | None = "20260318_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("external_uri", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column("version_label", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("meta", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_path", name="uq_knowledge_sources_storage_path"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_sources_status_updated_at_desc ON knowledge_sources(status, updated_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_sources_collected_at_desc ON knowledge_sources(collected_at DESC)")


def downgrade() -> None:
    op.drop_index("idx_knowledge_sources_collected_at_desc", table_name="knowledge_sources")
    op.drop_index("idx_knowledge_sources_status_updated_at_desc", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
