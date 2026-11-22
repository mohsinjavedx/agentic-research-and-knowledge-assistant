"""Bounded adjacent context; ranked hits and original source identities stay distinct."""

import asyncio
import logging
from dataclasses import dataclass, field, replace
from uuid import UUID

from sqlalchemy import or_, select

from app.core.config import Settings
from app.db.models import Chunk
from app.db.session import Database
from app.providers.reranking import Reranker, RerankerError
from app.schemas.retrieval import ContextGroup
from app.services.retrieval.dense import RetrievedChunk, validate_query_vector
from app.services.retrieval.search import retrieve_evidence


@dataclass
class RetrievalResult:
    ranked: list[RetrievedChunk]
    evidence: list[RetrievedChunk]
    context_groups: list[ContextGroup] = field(default_factory=list)
    reranking_applied: bool = False
    reranker_error: str | None = None


async def expand_adjacent(
    database: Database,
    query_vector: list[float],
    ranked: list[RetrievedChunk],
    allowed_doc_ids: list[UUID],
    *,
    minimum_similarity: float,
    similarity_margin: float = 0.05,
    max_extra: int = 5,
) -> RetrievalResult:
    validate_query_vector(query_vector)
    if not 0 <= max_extra <= 5 or not 0 <= similarity_margin <= 1:
        raise ValueError("Invalid adjacent context limits.")
    if any(row.document_id not in allowed_doc_ids for row in ranked):
        raise ValueError("Ranked evidence is outside the allowed document scope.")
    anchors = [row for row in ranked if row.cosine_similarity > minimum_similarity]
    if not anchors:
        return RetrievalResult(ranked, list(ranked))
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    statement = select(Chunk, distance).where(
        Chunk.document_id.in_(allowed_doc_ids),
        or_(
            *(
                (Chunk.document_id == row.document_id)
                & Chunk.chunk_index.in_([row.chunk_index - 1, row.chunk_index + 1])
                for row in anchors
            )
        ),
    )
    async with database.sessions() as session:
        rows = (await session.execute(statement)).all()
    neighbors = [
        RetrievedChunk(
            chunk.id,
            chunk.document_id,
            chunk.page_start,
            chunk.chunk_index,
            chunk.normalized_text,
            1.0 - float(cosine_distance),
        )
        for chunk, cosine_distance in rows
    ]
    edges = [
        (anchor.chunk_id, neighbor.chunk_id)
        for anchor in anchors
        for neighbor in neighbors
        if neighbor.document_id == anchor.document_id
        and abs(neighbor.chunk_index - anchor.chunk_index) == 1
        and neighbor.cosine_similarity > minimum_similarity
        and neighbor.cosine_similarity >= anchor.cosine_similarity - similarity_margin
    ]
    core_ids = {row.chunk_id for row in ranked}
    eligible = {identity for edge in edges for identity in edge}
    extras = sorted(
        (row for row in neighbors if row.chunk_id not in core_ids and row.chunk_id in eligible),
        key=lambda row: (-row.cosine_similarity, row.chunk_id),
    )[:max_extra]
    pool = {row.chunk_id: row for row in [*ranked, *extras]}
    graph: dict[UUID, set[UUID]] = {}
    for left, right in edges:
        if left in pool and right in pool:
            graph.setdefault(left, set()).add(right)
            graph.setdefault(right, set()).add(left)
    memberships: dict[UUID, UUID] = {}
    groups: list[ContextGroup] = []
    for core in ranked:
        if core.chunk_id not in graph or core.chunk_id in memberships:
            continue
        pending, members = [core.chunk_id], set()
        while pending:
            identity = pending.pop()
            if identity not in members:
                members.add(identity)
                pending.extend(graph[identity] - members)
        ordered = sorted(members, key=lambda identity: pool[identity].chunk_index)
        memberships.update(dict.fromkeys(members, core.chunk_id))
        groups.append(
            ContextGroup(anchor_id=core.chunk_id, document_id=core.document_id, chunk_ids=ordered)
        )
    evidence = [
        replace(
            row,
            context_group=memberships.get(row.chunk_id),
            is_adjacent_context=row.chunk_id not in core_ids,
        )
        for row in [*ranked, *extras]
    ]
    return RetrievalResult(evidence[: len(ranked)], evidence, groups)


async def retrieve_context(
    database: Database,
    query_vector: list[float],
    query: str,
    allowed_doc_ids: list[UUID],
    settings: Settings,
    *,
    top_k: int = 5,
    reranker: Reranker | None = None,
) -> RetrievalResult:
    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20.")
    ranked = await retrieve_evidence(
        database,
        query_vector,
        query,
        allowed_doc_ids,
        top_k=20 if settings.enable_reranker else top_k,
        mode=settings.retrieval_mode,
    )
    applied, error = False, None
    if settings.enable_reranker and ranked:
        try:
            if reranker is None:
                raise RerankerError("RERANKER_UNAVAILABLE")
            ranked = await asyncio.to_thread(reranker.rerank, query, ranked)
            applied = True
        except RerankerError as exc:
            error = exc.error_code
            logging.getLogger("research.retrieval").warning(
                "retrieval.reranker_fallback", extra={"error_code": error}
            )
    ranked = ranked[:top_k]
    if not settings.enable_context_expansion:
        return RetrievalResult(
            ranked, list(ranked), reranking_applied=applied, reranker_error=error
        )
    result = await expand_adjacent(
        database,
        query_vector,
        ranked,
        allowed_doc_ids,
        minimum_similarity=settings.retrieval_similarity_threshold,
        similarity_margin=settings.adjacency_similarity_margin,
        max_extra=settings.max_adjacent_chunks,
    )
    result.reranking_applied, result.reranker_error = applied, error
    return result
