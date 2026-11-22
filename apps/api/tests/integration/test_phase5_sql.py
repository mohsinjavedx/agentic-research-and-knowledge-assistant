import asyncio
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event

from app.core.config import load_settings
from app.db.models import Document
from app.db.session import Database
from app.services.indexing.service import persist_document
from app.services.retrieval.hybrid import retrieve_hybrid, retrieve_keywords
from tests.integration.test_indexing import batch

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"),
]


def test_hybrid_fuses_in_one_scoped_sql_roundtrip_with_correct_reciprocal_ranks() -> None:
    async def run() -> None:
        database = Database(load_settings())
        owned, foreign = batch(), batch()
        statements: list[str] = []

        def observe(connection, cursor, statement, parameters, context, executemany):
            if "chunks" in statement.lower():
                statements.append(statement)

        try:
            await persist_document(database, owned, filename="sql-owned.pdf", session_id=uuid4())
            await persist_document(
                database, foreign, filename="sql-foreign.pdf", session_id=uuid4()
            )
            event.listen(database.engine.sync_engine, "before_cursor_execute", observe)
            results = await retrieve_hybrid(
                database, [1.0] + [0.0] * 383, "stellar spectra", [owned.document_id]
            )
            assert results[0].chunk_id == UUID(owned.chunks[1].id)
            assert results[0].fusion_score == pytest.approx(1 / 62 + 1 / 61)
            assert results[0].cosine_similarity == pytest.approx(0.0)
            assert {row.document_id for row in results} == {owned.document_id}
            assert len(statements) == 1
            statements.clear()
            dense_fallback = await retrieve_hybrid(
                database, [1.0] + [0.0] * 383, "zznonmatchingterm", [owned.document_id], top_k=1
            )
            assert len(dense_fallback) == 1
            assert dense_fallback[0].chunk_id == UUID(owned.chunks[0].id)
            assert dense_fallback[0].fusion_score == pytest.approx(1 / 61)
        finally:
            event.remove(database.engine.sync_engine, "before_cursor_execute", observe)
            async with database.sessions() as session, session.begin():
                await session.execute(
                    delete(Document).where(
                        Document.id.in_([owned.document_id, foreign.document_id])
                    )
                )
            await database.close()

    asyncio.run(run())


def test_keyword_branch_respects_websearch_negation_instead_of_or_rewriting() -> None:
    async def run() -> None:
        database = Database(load_settings())
        owned = batch()
        try:
            await persist_document(database, owned, filename="websearch.pdf", session_id=uuid4())
            results = await retrieve_keywords(
                database, [1.0] + [0.0] * 383, "lexical -stellar", [owned.document_id]
            )
            assert [row.chunk_id for row in results] == [UUID(owned.chunks[0].id)]
        finally:
            async with database.sessions() as session, session.begin():
                await session.execute(delete(Document).where(Document.id == owned.document_id))
            await database.close()

    asyncio.run(run())
