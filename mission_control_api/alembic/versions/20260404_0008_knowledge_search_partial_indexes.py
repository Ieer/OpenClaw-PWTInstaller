"""add partial indexes for knowledge search

Revision ID: 20260404_0008
Revises: 20260404_0007
Create Date: 2026-04-04
"""

from typing import Sequence

from alembic import op


revision: str = "20260404_0008"
down_revision: str | None = "20260404_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("idx_knowledge_unit_embeddings_model_updated_at_desc", table_name="knowledge_unit_embeddings")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_unit_embeddings_model_dimensions_updated_at_desc
        ON knowledge_unit_embeddings(embedding_model, embedding_dimensions, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_unit_embeddings_bge_m3_1024_cosine_hnsw
        ON knowledge_unit_embeddings
        USING hnsw ((embedding::vector(1024)) vector_cosine_ops)
        WHERE embedding_model = 'bge-m3:latest' AND embedding_dimensions = 1024
        """
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_unit_embeddings_bge_m3_1024_cosine_hnsw", table_name="knowledge_unit_embeddings")
    op.drop_index("idx_knowledge_unit_embeddings_model_dimensions_updated_at_desc", table_name="knowledge_unit_embeddings")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_unit_embeddings_model_updated_at_desc
        ON knowledge_unit_embeddings(embedding_model, updated_at DESC)
        """
    )