"""add knowledge unit embeddings table

Revision ID: 20260404_0006
Revises: 20260401_0005
Create Date: 2026-04-04
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_0006"
down_revision: str | None = "20260401_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE knowledge_unit_embeddings (
          id uuid PRIMARY KEY,
          unit_id uuid NOT NULL REFERENCES knowledge_units(id) ON DELETE CASCADE,
          embedding_model text NOT NULL,
          embedding_dimensions integer NOT NULL DEFAULT 1536,
          content_sha256 text NOT NULL,
          embedding vector(1536) NOT NULL,
          meta jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_knowledge_unit_embeddings_unit_model UNIQUE (unit_id, embedding_model)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_unit_embeddings_unit_id ON knowledge_unit_embeddings(unit_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_unit_embeddings_model_updated_at_desc ON knowledge_unit_embeddings(embedding_model, updated_at DESC)"
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_unit_embeddings_model_updated_at_desc", table_name="knowledge_unit_embeddings")
    op.drop_index("idx_knowledge_unit_embeddings_unit_id", table_name="knowledge_unit_embeddings")
    op.drop_table("knowledge_unit_embeddings")