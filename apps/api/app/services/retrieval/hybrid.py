"""Scoped vector/keyword candidates combined by reciprocal rank fusion."""

from collections.abc import Sequence
from dataclasses import replace
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select, union_all

from app.db.models import Chunk
from app.db.session import Database
from app.services.retrieval.dense import RetrievedChunk, validate_query_vector

CANDIDATES_PER_BRANCH = 20
RRF_CONSTANT = 60


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
    if not allowed_doc_ids or not query.strip():
        return []
    parsed_query = func.websearch_to_tsquery("english", query)
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


def hybrid_statement(
    query_vector: list[float], query: str, allowed_doc_ids: list[UUID], top_k: int
) -> Select[Any]:
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    vector_top = (
        select(Chunk.id, distance)
        .where(Chunk.document_id.in_(allowed_doc_ids))
        .order_by(distance, Chunk.id)
        .limit(CANDIDATES_PER_BRANCH)
        .cte("vector_top")
    )
    parsed_query = func.websearch_to_tsquery("english", query)
    lexical_score = func.ts_rank_cd(Chunk.fts_tokens, parsed_query).label("lexical_score")
    lexical_top = (
        select(Chunk.id, lexical_score)
        .where(Chunk.document_id.in_(allowed_doc_ids), Chunk.fts_tokens.op("@@")(parsed_query))
        .order_by(lexical_score.desc(), Chunk.id)
        .limit(CANDIDATES_PER_BRANCH)
        .cte("lexical_top")
    )
    vector_ranks = select(
        vector_top.c.id,
        func.row_number().over(order_by=(vector_top.c.distance, vector_top.c.id)).label("rank"),
    ).cte("vector_ranks")
    lexical_ranks = select(
        lexical_top.c.id,
        func.row_number()
        .over(order_by=(lexical_top.c.lexical_score.desc(), lexical_top.c.id))
        .label("rank"),
    ).cte("lexical_ranks")
    votes = union_all(select(vector_ranks), select(lexical_ranks)).cte("rank_votes")
    fused = (
        select(
            votes.c.id,
            func.sum(1.0 / (RRF_CONSTANT + votes.c.rank)).label("fusion_score"),
            func.min(votes.c.rank).label("best_rank"),
        )
        .group_by(votes.c.id)
        .cte("fused")
    )
    return (
        select(Chunk, distance, fused.c.fusion_score)
        .join(fused, fused.c.id == Chunk.id)
        .order_by(fused.c.fusion_score.desc(), fused.c.best_rank, Chunk.id)
        .limit(top_k)
    )


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
    async with database.sessions() as session:
        rows = (
            await session.execute(hybrid_statement(query_vector, query, allowed_doc_ids, top_k))
        ).all()
    return [
        RetrievedChunk(
            chunk_id=item.id,
            document_id=item.document_id,
            page_number=item.page_start,
            chunk_index=item.chunk_index,
            text=item.normalized_text,
            cosine_similarity=1.0 - float(cosine_distance),
            fusion_score=float(score),
        )
        for item, cosine_distance, score in rows
    ]
