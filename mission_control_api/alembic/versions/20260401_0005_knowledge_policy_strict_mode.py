"""add strict_mode to knowledge validation policies

Revision ID: 20260401_0005
Revises: 20260331_0004
Create Date: 2026-04-01
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260401_0005"
down_revision: str | None = "20260331_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_validation_policies",
        sa.Column("strict_mode", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("knowledge_validation_policies", "strict_mode")
