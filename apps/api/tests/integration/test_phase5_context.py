import asyncio
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from app.core.config import load_settings
from app.db.models import Document
from app.db.session import Database
from app.services.indexing.service import persist_document
from app.services.retrieval.context import expand_adjacent
from app.services.retrieval.dense import retrieve_chunks
from tests.integration.test_indexing import batch

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"),
]


def test_adjacent_expansion_is_bounded_high_score_same_document_and_keeps_source_identity() -> None:
    async def run() -> None:
        database = Database(load_settings())
        owned, foreign = batch(), batch()
        vector = [2**-0.5, 2**-0.5] + [0.0] * 382
        try:
            await persist_document(
                database, owned, filename="adjacent-owned.pdf", session_id=uuid4()
            )
            await persist_document(
                database, foreign, filename="adjacent-foreign.pdf", session_id=uuid4()
            )
            originals = await retrieve_chunks(database, vector, [owned.document_id], top_k=2)
            first = next(row for row in originals if row.chunk_index == 0)
            last = next(row for row in originals if row.chunk_index == 1)
            result = await expand_adjacent(
                database,
                vector,
                [first],
                [owned.document_id],
                minimum_similarity=0.6,
                similarity_margin=0.05,
                max_extra=5,
            )
            assert len(result.ranked) == 1 and len(result.evidence) == 2
            assert {row.chunk_id for row in result.evidence} == {
                UUID(row.id) for row in owned.chunks
            }
            assert {row.document_id for row in result.evidence} == {owned.document_id}
            assert result.evidence[0].text == first.text
            assert result.evidence[1].text == last.text
            assert result.evidence[1].is_adjacent_context is True
            assert result.context_groups[0].chunk_ids == [first.chunk_id, last.chunk_id]
            reverse = await expand_adjacent(
                database,
                vector,
                [last],
                [owned.document_id],
                minimum_similarity=0.6,
                similarity_margin=0.05,
                max_extra=1,
            )
            assert reverse.context_groups[0].chunk_ids == [first.chunk_id, last.chunk_id]
            both = await expand_adjacent(
                database,
                vector,
                [last, first],
                [owned.document_id],
                minimum_similarity=0.6,
                similarity_margin=0.05,
                max_extra=1,
            )
            assert len(both.evidence) == 2
            assert len(both.context_groups) == 1
            rejected = await expand_adjacent(
                database,
                vector,
                [first],
                [owned.document_id],
                minimum_similarity=0.8,
                similarity_margin=0.05,
                max_extra=5,
            )
            assert len(rejected.evidence) == 1 and not rejected.context_groups
            bounded = await expand_adjacent(
                database,
                vector,
                [first],
                [owned.document_id],
                minimum_similarity=0.6,
                max_extra=0,
            )
            assert len(bounded.evidence) == 1 and not bounded.context_groups
            # Both chunks clear the absolute threshold, but the neighbor trails
            # by more than the relative margin. It must not be expanded.
            uneven = await retrieve_chunks(
                database, [1.0] + [0.0] * 383, [owned.document_id], top_k=2
            )
            relative = await expand_adjacent(
                database,
                [1.0] + [0.0] * 383,
                uneven[:1],
                [owned.document_id],
                minimum_similarity=-0.1,
                similarity_margin=0.05,
            )
            assert len(relative.evidence) == 1 and not relative.context_groups
            with pytest.raises(ValueError, match="scope"):
                await expand_adjacent(
                    database,
                    vector,
                    [first],
                    [foreign.document_id],
                    minimum_similarity=0.6,
                    similarity_margin=0.05,
                    max_extra=5,
                )
        finally:
            async with database.sessions() as session, session.begin():
                await session.execute(
                    delete(Document).where(
                        Document.id.in_([owned.document_id, foreign.document_id])
                    )
                )
            await database.close()

    asyncio.run(run())
