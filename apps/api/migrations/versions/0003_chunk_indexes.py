"""Create reproducible embedding batches and unified vector/full-text chunks."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0003_chunk_indexes"
down_revision = "0002_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "embedding_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("embedding_model", sa.String(255), nullable=False),
        sa.Column("model_revision", sa.String(128), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(8), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", name="uq_embedding_batches_document"),
        sa.UniqueConstraint("id", "document_id", name="uq_embedding_batches_identity_document"),
        sa.CheckConstraint("embedding_dim = 384", name="ck_embedding_batches_dimension"),
        sa.CheckConstraint("chunk_count > 0", name="ck_embedding_batches_count"),
        sa.CheckConstraint("provider IN ('local','api')", name="ck_embedding_batches_provider"),
        sa.CheckConstraint(
            "length(embedding_model) > 0 AND length(model_revision) > 0",
            name="ck_embedding_batches_identity",
        ),
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("chunk_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "fts_tokens",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english'::regconfig, normalized_text)", persisted=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["batch_id", "document_id"],
            ["embedding_batches.id", "embedding_batches.document_id"],
            name="fk_chunks_batch_document",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_chunks_index"),
        sa.CheckConstraint(
            "page_start BETWEEN 1 AND 100 AND page_end = page_start", name="ck_chunks_pages"
        ),
        sa.CheckConstraint(
            "char_start >= 0 AND char_end > char_start "
            "AND char_length(raw_text) = char_end - char_start",
            name="ck_chunks_span",
        ),
        sa.CheckConstraint("char_length(normalized_text) > 0", name="ck_chunks_text"),
    )
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )
    op.create_index("ix_chunks_fts_gin", "chunks", ["fts_tokens"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_chunks_fts_gin", table_name="chunks")
    op.drop_index("ix_chunks_embedding_hnsw", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("embedding_batches")
