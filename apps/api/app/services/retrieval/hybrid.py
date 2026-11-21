"""Scoped vector/keyword candidates combined by reciprocal rank fusion."""

import asyncio
import re
from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

from sqlalchemy import func, select

from app.db.models import Chunk
from app.db.session import Database
from app.services.retrieval.dense import RetrievedChunk, retrieve_chunks, validate_query_vector

CANDIDATES_PER_BRANCH = 20


def fuse_rankings(
    rankings: Sequence[Sequence[RetrievedChunk]], *, top_k: int = 5, rank_constant: int = 60
) -> list[RetrievedChunk]:
    if not 1 <= top_k <= 20 or rank_constant < 1:
        raise ValueError("Invalid fusion limits.")
    scores: dict[UUID, float] = {}
    sources: dict[UUID, RetrievedChunk] = {}
    best_ranks: dict[UUID, int] = {}
    for ranking in rankings:
        seen: set[UUID] = set()
        for rank, item in enumerate(ranking, start=1):
            if item.chunk_id in seen:
                continue
            seen.add(item.chunk_id)
            sources.setdefault(item.chunk_id, item)
            scores[item.chunk_id] = scores.get(item.chunk_id, 0.0) + 1 / (rank_constant + rank)
            best_ranks[item.chunk_id] = min(best_ranks.get(item.chunk_id, rank), rank)
    ordered = sorted(scores, key=lambda key: (-scores[key], best_ranks[key], str(key)))
    return [replace(sources[key], fusion_score=scores[key]) for key in ordered[:top_k]]


async def retrieve_keywords(
    database: Database, query_vector: list[float], query: str, allowed_doc_ids: list[UUID]
) -> list[RetrievedChunk]:
    validate_query_vector(query_vector)
    # OR candidates avoid requiring every word of a natural-language question.
    # Tokenization removes websearch operators; the value remains a bound SQL parameter.
    words = list(dict.fromkeys(re.findall(r"[^\W_]+", query.lower())))[:64]
    if not allowed_doc_ids or not words:
        return []
    parsed_query = func.websearch_to_tsquery("english", " OR ".join(words))
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    rank = func.ts_rank_cd(Chunk.fts_tokens, parsed_query)
    statement = (
        select(Chunk, distance)
        .where(Chunk.document_id.in_(allowed_doc_ids), Chunk.fts_tokens.op("@@")(parsed_query))
        .order_by(rank.desc(), Chunk.id)
        .limit(CANDIDATES_PER_BRANCH)
    )
    async with database.sessions() as session:
        rows = (await session.execute(statement)).all()
    return [
        RetrievedChunk(
            chunk_id=item.id,
            document_id=item.document_id,
            page_number=item.page_start,
            chunk_index=item.chunk_index,
            text=item.normalized_text,
            cosine_similarity=1.0 - float(cosine_distance),
        )
        for item, cosine_distance in rows
    ]


async def retrieve_hybrid(
    database: Database,
    query_vector: list[float],
    query: str,
    allowed_doc_ids: list[UUID],
    *,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20.")
    validate_query_vector(query_vector)
    if not allowed_doc_ids:
        return []
    dense, lexical = await asyncio.gather(
        retrieve_chunks(database, query_vector, allowed_doc_ids, top_k=CANDIDATES_PER_BRANCH),
        retrieve_keywords(database, query_vector, query, allowed_doc_ids),
    )
    return fuse_rankings([dense, lexical], top_k=top_k)
