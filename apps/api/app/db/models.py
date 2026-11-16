"""Durable ingestion status; vector/chunk indexes arrive in Phase 2."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Uuid, func, text
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
