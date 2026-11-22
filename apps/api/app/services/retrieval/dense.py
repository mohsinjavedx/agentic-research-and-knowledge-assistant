"""Session-scoped dense retrieval using PostgreSQL cosine distance."""

import asyncio
import math
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from app.db.models import Chunk
from app.db.session import Database
from app.providers.embeddings import EmbeddingProvider


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    page_number: int
    chunk_index: int
    text: str
    cosine_similarity: float
    fusion_score: float | None = None
    context_group: UUID | None = None
    is_adjacent_context: bool = False
    rerank_score: float | None = None


def validate_query_vector(query_vector: list[float]) -> None:
    if len(query_vector) != 384 or any(not math.isfinite(value) for value in query_vector):
        raise ValueError("Query embedding must contain 384 finite values.")
    if not any(value != 0 for value in query_vector):
        raise ValueError("Query embedding must not be a zero vector.")


async def retrieve_chunks(
    database: Database,
    query_vector: list[float],
    allowed_doc_ids: list[UUID],
    *,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20.")
    validate_query_vector(query_vector)
    if not allowed_doc_ids:
        return []

    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    statement = (
        select(Chunk, distance)
        .where(Chunk.document_id.in_(allowed_doc_ids))
        .order_by(distance, Chunk.id)
        .limit(top_k)
    )
    async with database.sessions() as session:
        rows = (await session.execute(statement)).all()
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            page_number=chunk.page_start,
            chunk_index=chunk.chunk_index,
            text=chunk.normalized_text,
            cosine_similarity=1.0 - float(cosine_distance),
        )
        for chunk, cosine_distance in rows
    ]


async def search_chunks(
    database: Database,
    provider: EmbeddingProvider,
    query: str,
    allowed_doc_ids: list[UUID],
    *,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    query_vector = await asyncio.to_thread(provider.embed_query, query)
    return await retrieve_chunks(database, query_vector, allowed_doc_ids, top_k=top_k)
