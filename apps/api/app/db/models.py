"""Durable document status, reproducible embedding batches and unified chunk indexes."""

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','processing','ready','failed')", name="ck_documents_status"
        ),
        CheckConstraint("is_sample OR session_id IS NOT NULL", name="ck_documents_owner"),
        CheckConstraint(
            "page_count IS NULL OR page_count BETWEEN 1 AND 100", name="ck_documents_pages"
        ),
        Index("ix_documents_status_updated_at", "status", "updated_at"),
        Index(
            "uq_documents_session_checksum",
            "session_id",
            "checksum",
            unique=True,
            postgresql_where=text("NOT is_sample AND session_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    filename: Mapped[str] = mapped_column(String(255))
    checksum: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), server_default="queued")
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmbeddingBatch(Base):
    __tablename__ = "embedding_batches"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_embedding_batches_document"),
        UniqueConstraint("id", "document_id", name="uq_embedding_batches_identity_document"),
        CheckConstraint("embedding_dim = 384", name="ck_embedding_batches_dimension"),
        CheckConstraint("chunk_count > 0", name="ck_embedding_batches_count"),
        CheckConstraint("provider IN ('local','api')", name="ck_embedding_batches_provider"),
        CheckConstraint(
            "length(embedding_model) > 0 AND length(model_revision) > 0",
            name="ck_embedding_batches_identity",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"))
    embedding_model: Mapped[str] = mapped_column(String(255))
    model_revision: Mapped[str] = mapped_column(String(128))
    embedding_dim: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(8))
    chunk_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["batch_id", "document_id"],
            ["embedding_batches.id", "embedding_batches.document_id"],
            name="fk_chunks_batch_document",
            ondelete="CASCADE",
        ),
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
        CheckConstraint("chunk_index >= 0", name="ck_chunks_index"),
        CheckConstraint(
            "page_start BETWEEN 1 AND 100 AND page_end = page_start", name="ck_chunks_pages"
        ),
        CheckConstraint(
            "char_start >= 0 AND char_end > char_start "
            "AND char_length(raw_text) = char_end - char_start",
            name="ck_chunks_span",
        ),
        CheckConstraint("char_length(normalized_text) > 0", name="ck_chunks_text"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
        Index("ix_chunks_fts_gin", "fts_tokens", postgresql_using="gin"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"))
    batch_id: Mapped[UUID] = mapped_column(Uuid)
    chunk_index: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    chunk_metadata: Mapped[dict[str, str | int | float | bool]] = mapped_column(JSONB)
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
    fts_tokens: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english'::regconfig, normalized_text)", persisted=True)
    )
