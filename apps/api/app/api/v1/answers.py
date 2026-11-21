"""Session-scoped grounded answers with verified citations and evidence fallback."""

import asyncio
import logging
from time import perf_counter

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.sessions import require_session_id
from app.core.config import Settings
from app.db.session import Database
from app.providers.embeddings import (
    EmbeddingInputTooLong,
    EmbeddingProvider,
    EmbeddingProviderError,
)
from app.providers.llm import LLMProvider, LLMProviderError
from app.schemas.answers import AnswerRequest, AnswerResponse
from app.services.generation.answer import generate_answer
from app.services.retrieval.dense import RetrievedChunk
from app.services.retrieval.scope import visible_document_ids
from app.services.retrieval.search import retrieve_evidence

logger = logging.getLogger("research.generation")
router = APIRouter(prefix="/api/v1", tags=["answers"])


@router.post("/answer", response_model=AnswerResponse)
async def answer(request: Request, body: AnswerRequest, response: Response) -> AnswerResponse:
    started_at = perf_counter()
    scope_ms = 0.0
    embedding_ms = 0.0
    vector_search_ms = 0.0
    generation_ms = 0.0
    evidence: list[RetrievedChunk] = []
    llm_called = False
    session_id = require_session_id(request)
    database: Database = request.app.state.database
    embedding_provider: EmbeddingProvider = request.app.state.embedding_provider
    llm_provider: LLMProvider = request.app.state.llm_provider
    settings: Settings = request.app.state.settings

    try:
        stage_started_at = perf_counter()
        allowed_doc_ids = await visible_document_ids(database, session_id, body.document_ids)
        scope_ms = (perf_counter() - stage_started_at) * 1000
        if body.document_ids is not None and len(allowed_doc_ids) != len(body.document_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        stage_started_at = perf_counter()
        query_vector = await asyncio.to_thread(embedding_provider.embed_query, body.query)
        embedding_ms = (perf_counter() - stage_started_at) * 1000

        stage_started_at = perf_counter()
        evidence = await retrieve_evidence(
            database,
            query_vector,
            body.query,
            allowed_doc_ids,
            top_k=body.top_k,
            mode=settings.retrieval_mode,
        )
        vector_search_ms = (perf_counter() - stage_started_at) * 1000

        llm_called = bool(
            evidence
            and max(item.cosine_similarity for item in evidence)
            > settings.retrieval_similarity_threshold
        )
        stage_started_at = perf_counter()
        try:
            result = await generate_answer(
                llm_provider,
                body.query,
                evidence,
                similarity_threshold=settings.retrieval_similarity_threshold,
            )
        finally:
            generation_ms = (perf_counter() - stage_started_at) * 1000

        timings = (
            ("scope", scope_ms),
            ("embedding", embedding_ms),
            ("vector_search", vector_search_ms),
            ("generation", generation_ms),
            ("total", (perf_counter() - started_at) * 1000),
        )
        response.headers["Server-Timing"] = ", ".join(
            f"{name};dur={duration:.2f}" for name, duration in timings
        )
        return result
    except EmbeddingInputTooLong:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query exceeds the embedding model's token limit.",
        ) from None
    except EmbeddingProviderError as exc:
        logger.error("answer.embedding_failed", extra={"error_code": exc.error_code})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer generation is temporarily unavailable.",
        ) from None
    except LLMProviderError as exc:
        logger.error("answer.llm_failed", extra={"error_code": exc.error_code})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer generation is temporarily unavailable.",
        ) from None
    except SQLAlchemyError:
        logger.error("answer.database_failed", extra={"error_code": "DATABASE_OPERATION_FAILED"})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer generation is temporarily unavailable.",
        ) from None
    finally:
        logger.info(
            "answer.timing",
            extra={
                "scope_ms": round(scope_ms, 2),
                "embedding_ms": round(embedding_ms, 2),
                "vector_search_ms": round(vector_search_ms, 2),
                "generation_ms": round(generation_ms, 2),
                "total_ms": round((perf_counter() - started_at) * 1000, 2),
                "evidence_count": len(evidence),
                "llm_called": llm_called,
            },
        )
