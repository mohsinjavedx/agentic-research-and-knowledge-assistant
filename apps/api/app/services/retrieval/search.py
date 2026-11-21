"""Shared retrieval strategy dispatch for search and answer routes."""

import asyncio
from typing import Literal
from uuid import UUID

from app.db.session import Database
from app.providers.embeddings import EmbeddingProvider
from app.services.retrieval.dense import RetrievedChunk, retrieve_chunks
from app.services.retrieval.hybrid import retrieve_hybrid

RetrievalMode = Literal["dense", "hybrid"]


async def retrieve_evidence(
    database: Database,
    query_vector: list[float],
    query: str,
    allowed_doc_ids: list[UUID],
    *,
    top_k: int = 5,
    mode: RetrievalMode = "dense",
) -> list[RetrievedChunk]:
    if mode == "hybrid":
        return await retrieve_hybrid(database, query_vector, query, allowed_doc_ids, top_k=top_k)
    if mode != "dense":
        raise ValueError("Unsupported retrieval mode.")
    return await retrieve_chunks(database, query_vector, allowed_doc_ids, top_k=top_k)


async def search_evidence(
    database: Database,
    provider: EmbeddingProvider,
    query: str,
    allowed_doc_ids: list[UUID],
    *,
    top_k: int = 5,
    mode: RetrievalMode = "dense",
) -> list[RetrievedChunk]:
    query_vector = await asyncio.to_thread(provider.embed_query, query)
    return await retrieve_evidence(
        database, query_vector, query, allowed_doc_ids, top_k=top_k, mode=mode
    )
