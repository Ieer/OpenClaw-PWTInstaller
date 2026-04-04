"""allow variable dimensions for knowledge unit embeddings

Revision ID: 20260404_0007
Revises: 20260404_0006
Create Date: 2026-04-04
"""

from typing import Sequence

from alembic import op


revision: str = "20260404_0007"
down_revision: str | None = "20260404_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE knowledge_unit_embeddings ALTER COLUMN embedding TYPE vector USING embedding::vector"
    )
    op.execute(
        "ALTER TABLE knowledge_unit_embeddings ALTER COLUMN embedding_dimensions DROP DEFAULT"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE knowledge_unit_embeddings ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)"
    )
    op.execute(
        "ALTER TABLE knowledge_unit_embeddings ALTER COLUMN embedding_dimensions SET DEFAULT 1536"
    )