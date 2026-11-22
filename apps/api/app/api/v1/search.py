"""Session-scoped dense evidence search."""

import asyncio
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
from app.services.retrieval.context import retrieve_context
from app.services.retrieval.scope import visible_document_ids

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
        query_vector = await asyncio.to_thread(provider.embed_query, body.query)
        retrieval = await retrieve_context(
            database,
            query_vector,
            body.query,
            allowed_doc_ids,
            settings,
            top_k=body.top_k,
            reranker=request.app.state.reranker,
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
    results = retrieval.ranked
    insufficient_evidence = (
        not results or max(item.cosine_similarity for item in results) <= threshold
    )
    return SearchResponse(
        results=[SearchResult.model_validate(result) for result in results],
        similarity_threshold=threshold,
        insufficient_evidence=insufficient_evidence,
        retrieval_mode=settings.retrieval_mode,
        adjacent_context=[
            SearchResult.model_validate(row)
            for row in retrieval.evidence
            if row.is_adjacent_context
        ],
        context_groups=retrieval.context_groups,
        reranking_applied=retrieval.reranking_applied,
        reranker_error=retrieval.reranker_error,
    )
