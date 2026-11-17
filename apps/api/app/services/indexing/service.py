"""Persist validated document embeddings and their source chunks atomically."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text

from app.core.config import Settings
from app.db.embedding_compatibility import assert_batch_model_compatibility
from app.db.locks import EMBEDDING_INDEX_ADVISORY_LOCK
from app.db.models import Chunk, Document, EmbeddingBatch
from app.db.session import Database
from app.providers.identity import (
    BGE_MODEL,
    BGE_REVISION,
    EMBEDDING_DIMENSION,
    EmbeddingCompatibilityError,
    EmbeddingIdentity,
)
from app.schemas.chunks import ChunkSchema


@dataclass(frozen=True)
class EmbeddedDocument:
    document_id: UUID
    checksum: str
    page_count: int
    chunks: tuple[ChunkSchema, ...]
    vectors: tuple[tuple[float, ...], ...]
    identity: EmbeddingIdentity
    provider: str


def _validate_document(
    embedded: EmbeddedDocument, *, is_sample: bool, session_id: UUID | None
) -> None:
    if is_sample == (session_id is not None):
        raise ValueError("Choose exactly one document scope: sample or session.")
    if (
        embedded.identity.model != BGE_MODEL
        or embedded.identity.revision != BGE_REVISION
        or embedded.identity.dimension != EMBEDDING_DIMENSION
    ):
        raise EmbeddingCompatibilityError("UNSUPPORTED_EMBEDDING_MODEL")
    if embedded.provider not in {"local", "api"}:
        raise ValueError("Unsupported embedding provider.")
    if len(embedded.checksum) != 64 or any(
        character not in "0123456789abcdef" for character in embedded.checksum
    ):
        raise ValueError("Document checksum must be a lowercase SHA-256 digest.")
    if not 1 <= embedded.page_count <= 100 or not embedded.chunks:
        raise ValueError("Document must contain 1-100 pages and at least one chunk.")
    if len(embedded.chunks) != len(embedded.vectors):
        raise ValueError("Each document chunk must have exactly one embedding.")

    document_id = str(embedded.document_id)
    for index, (chunk, vector) in enumerate(zip(embedded.chunks, embedded.vectors, strict=True)):
        if chunk.document_id != document_id or chunk.chunk_index != index:
            raise ValueError("Chunk document IDs and indexes must match the embedded batch.")
        if not 1 <= chunk.page_start <= embedded.page_count:
            raise ValueError("Chunk page number is outside the document.")
        if len(vector) != EMBEDDING_DIMENSION or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in vector
        ):
            raise ValueError("Embedding vectors must contain 384 finite numeric values.")
        if not any(value != 0 for value in vector):
            raise ValueError("Embedding vectors must not be zero vectors.")


async def persist_document(
    database: Database,
    embedded: EmbeddedDocument,
    *,
    filename: str,
    is_sample: bool = False,
    session_id: UUID | None = None,
) -> UUID:
    """Persist once per session/checksum and return the canonical document ID."""
    _validate_document(embedded, is_sample=is_sample, session_id=session_id)
    if not filename or len(filename) > 255:
        raise ValueError("Filename must contain between 1 and 255 characters.")

    settings: Settings = database.settings
    expires_at = (
        datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours)
        if session_id is not None
        else None
    )
    async with database.sessions() as session, session.begin():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": EMBEDDING_INDEX_ADVISORY_LOCK},
        )
        await assert_batch_model_compatibility(session, embedded.identity)
        if session_id is not None:
            await session.execute(
                delete(Document).where(
                    Document.session_id == session_id,
                    Document.checksum == embedded.checksum,
                    Document.is_sample.is_(False),
                    Document.expires_at < func.now(),
                )
            )
            existing_id = await session.scalar(
                select(Document.id).where(
                    Document.session_id == session_id,
                    Document.checksum == embedded.checksum,
                    Document.is_sample.is_(False),
                )
            )
            if existing_id is not None:
                return existing_id

        batch_id = uuid4()
        session.add(
            Document(
                id=embedded.document_id,
                session_id=session_id,
                is_sample=is_sample,
                filename=filename,
                checksum=embedded.checksum,
                status="ready",
                page_count=embedded.page_count,
                expires_at=expires_at,
            )
        )
        session.add(
            EmbeddingBatch(
                id=batch_id,
                document_id=embedded.document_id,
                embedding_model=embedded.identity.model,
                model_revision=embedded.identity.revision,
                embedding_dim=embedded.identity.dimension,
                provider=embedded.provider,
                chunk_count=len(embedded.chunks),
            )
        )
        await session.flush()
        session.add_all(
            [
                Chunk(
                    id=UUID(chunk.id),
                    document_id=embedded.document_id,
                    batch_id=batch_id,
                    chunk_index=chunk.chunk_index,
                    raw_text=chunk.raw_text,
                    normalized_text=chunk.normalized_text,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    chunk_metadata=chunk.metadata,
                    embedding=list(vector),
                )
                for chunk, vector in zip(embedded.chunks, embedded.vectors, strict=True)
            ]
        )
    return embedded.document_id
