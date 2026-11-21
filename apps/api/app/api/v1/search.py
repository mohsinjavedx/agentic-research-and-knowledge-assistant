"""Session-scoped dense evidence search."""

import logging

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.sessions import require_session_id
from app.core.config import Settings
from app.db.session import Database
from app.providers.embeddings import (
    EmbeddingInputTooLong,
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.schemas.retrieval import SearchRequest, SearchResponse, SearchResult
from app.services.retrieval.scope import visible_document_ids
from app.services.retrieval.search import search_evidence

logger = logging.getLogger("research.retrieval")
router = APIRouter(prefix="/api/v1", tags=["retrieval"])


@router.post("/search", response_model=SearchResponse)
async def search(request: Request, body: SearchRequest) -> SearchResponse:
    session_id = require_session_id(request)
    database: Database = request.app.state.database
    provider: EmbeddingProvider = request.app.state.embedding_provider
    settings: Settings = request.app.state.settings

    try:
        allowed_doc_ids = await visible_document_ids(database, session_id, body.document_ids)
        if body.document_ids is not None and len(allowed_doc_ids) != len(body.document_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        results = await search_evidence(
            database,
            provider,
            body.query,
            allowed_doc_ids,
            top_k=body.top_k,
            mode=settings.retrieval_mode,
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
    insufficient_evidence = (
        not results or max(item.cosine_similarity for item in results) <= threshold
    )
    return SearchResponse(
        results=[
            SearchResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                page_number=result.page_number,
                chunk_index=result.chunk_index,
                text=result.text,
                cosine_similarity=round(result.cosine_similarity, 6),
                fusion_score=result.fusion_score,
            )
            for result in results
        ],
        similarity_threshold=threshold,
        insufficient_evidence=insufficient_evidence,
        retrieval_mode=settings.retrieval_mode,
    )
