"""add common model partial indexes for knowledge search

Revision ID: 20260404_0009
Revises: 20260404_0008
Create Date: 2026-04-04
"""

from typing import Sequence

from alembic import op


revision: str = "20260404_0009"
down_revision: str | None = "20260404_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_unit_embeddings_mxbai_1024_cosine_hnsw
        ON knowledge_unit_embeddings
        USING hnsw ((embedding::vector(1024)) vector_cosine_ops)
        WHERE embedding_model = 'mxbai-embed-large:latest' AND embedding_dimensions = 1024
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_unit_embeddings_nomic_768_cosine_hnsw
        ON knowledge_unit_embeddings
        USING hnsw ((embedding::vector(768)) vector_cosine_ops)
        WHERE embedding_model = 'nomic-embed-text:latest' AND embedding_dimensions = 768
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_unit_embeddings_all_minilm_384_cosine_hnsw
        ON knowledge_unit_embeddings
        USING hnsw ((embedding::vector(384)) vector_cosine_ops)
        WHERE embedding_model = 'all-minilm:latest' AND embedding_dimensions = 384
        """
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_unit_embeddings_all_minilm_384_cosine_hnsw", table_name="knowledge_unit_embeddings")
    op.drop_index("idx_knowledge_unit_embeddings_nomic_768_cosine_hnsw", table_name="knowledge_unit_embeddings")
    op.drop_index("idx_knowledge_unit_embeddings_mxbai_1024_cosine_hnsw", table_name="knowledge_unit_embeddings")