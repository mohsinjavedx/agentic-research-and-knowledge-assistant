"""Session-scoped dense evidence search."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.sessions import require_session_id
from app.core.config import Settings
from app.db.models import Document
from app.db.session import Database
from app.providers.embeddings import (
    EmbeddingInputTooLong,
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.schemas.retrieval import SearchRequest, SearchResponse, SearchResult
from app.services.retrieval.dense import search_chunks

logger = logging.getLogger("research.retrieval")
router = APIRouter(prefix="/api/v1", tags=["retrieval"])


async def _visible_document_ids(
    database: Database, session_id: UUID, requested_ids: list[UUID] | None
) -> list[UUID]:
    owner_scope = and_(
        Document.is_sample.is_(False),
        Document.session_id == session_id,
        or_(Document.expires_at.is_(None), Document.expires_at > func.now()),
    )
    statement = select(Document.id).where(
        Document.status == "ready",
        or_(Document.is_sample.is_(True), owner_scope),
    )
    if requested_ids is not None:
        statement = statement.where(Document.id.in_(requested_ids))
    async with database.sessions() as session:
        return list((await session.scalars(statement)).all())


@router.post("/search", response_model=SearchResponse)
async def search(request: Request, body: SearchRequest) -> SearchResponse:
    session_id = require_session_id(request)
    database: Database = request.app.state.database
    provider: EmbeddingProvider = request.app.state.embedding_provider
    settings: Settings = request.app.state.settings

    try:
        allowed_doc_ids = await _visible_document_ids(database, session_id, body.document_ids)
        if body.document_ids is not None and len(allowed_doc_ids) != len(body.document_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        results = await search_chunks(
            database, provider, body.query, allowed_doc_ids, top_k=body.top_k
        )
    except EmbeddingInputTooLong:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query exceeds the embedding model's token limit.",
        ) from None
    except EmbeddingProviderError as exc:
        logger.error("search.embedding_failed", extra={"error_code": exc.error_code})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable.",
        ) from None
    except SQLAlchemyError:
        logger.error("search.database_failed", extra={"error_code": "DATABASE_OPERATION_FAILED"})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable.",
        ) from None

    threshold = settings.retrieval_similarity_threshold
    insufficient_evidence = not results or results[0].cosine_similarity <= threshold
    return SearchResponse(
        results=[
            SearchResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                page_number=result.page_number,
                chunk_index=result.chunk_index,
                text=result.text,
                cosine_similarity=round(result.cosine_similarity, 6),
            )
            for result in results
        ],
        similarity_threshold=threshold,
        insufficient_evidence=insufficient_evidence,
    )
