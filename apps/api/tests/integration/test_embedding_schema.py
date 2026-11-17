import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text

from app.core.config import load_settings
from app.db.models import Document, EmbeddingBatch
from app.db.session import Database
from app.providers.identity import BGE_MODEL, BGE_REVISION, EmbeddingCompatibilityError

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 for real Postgres"
    ),
]


def test_actual_vector_column_and_generated_fts_indexes() -> None:
    async def run() -> None:
        database = Database(load_settings())
        try:
            assert await database.check()
            async with database.sessions() as session:
                assert (
                    await session.scalar(
                        text(
                            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                            "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
                        )
                    )
                    == "vector(384)"
                )
                indexes = dict(
                    (
                        await session.execute(
                            text(
                                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'chunks'"
                            )
                        )
                    ).all()
                )
                assert "USING hnsw" in indexes["ix_chunks_embedding_hnsw"]
                assert "vector_cosine_ops" in indexes["ix_chunks_embedding_hnsw"]
                assert "USING gin" in indexes["ix_chunks_fts_gin"]
                generated = await session.scalar(
                    text(
                        "SELECT is_generated FROM information_schema.columns "
                        "WHERE table_name = 'chunks' AND column_name = 'fts_tokens'"
                    )
                )
                assert generated == "ALWAYS"
        finally:
            await database.close()

    asyncio.run(run())


def test_database_check_rejects_persisted_model_or_revision_mismatch() -> None:
    async def run() -> None:
        database = Database(load_settings())
        identity = uuid4()
        try:
            async with database.sessions() as session, session.begin():
                session.add(
                    Document(
                        id=identity,
                        is_sample=True,
                        filename="model-test.pdf",
                        checksum="0" * 64,
                        status="ready",
                    )
                )
                await session.flush()
                session.add(
                    EmbeddingBatch(
                        document_id=identity,
                        embedding_model=BGE_MODEL,
                        model_revision="wrong-revision",
                        embedding_dim=384,
                        provider="local",
                        chunk_count=1,
                    )
                )
            with pytest.raises(EmbeddingCompatibilityError):
                await database.check()
            async with database.sessions() as session, session.begin():
                batch = await session.scalar(
                    select(EmbeddingBatch).where(EmbeddingBatch.document_id == identity)
                )
                assert batch is not None
                batch.model_revision = BGE_REVISION
            assert await database.check()
        finally:
            async with database.sessions() as session, session.begin():
                await session.execute(delete(Document).where(Document.id == identity))
            await database.close()

    asyncio.run(run())
