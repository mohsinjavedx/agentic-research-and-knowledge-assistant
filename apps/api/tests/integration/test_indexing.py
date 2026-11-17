import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import load_settings
from app.db.models import Chunk, Document, EmbeddingBatch
from app.db.session import Database
from app.providers.identity import EmbeddingIdentity
from app.schemas.chunks import ChunkSchema
from app.services.indexing.service import EmbeddedDocument, persist_document

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 for real Postgres"
    ),
]


def batch(document_id=None) -> EmbeddedDocument:
    identity = document_id or uuid4()
    prose = [
        "Hybrid retrieval combines lexical matching and vector similarity.",
        "An unrelated passage describes stellar spectra.",
    ]
    chunks = tuple(
        ChunkSchema(
            id=str(uuid4()),
            document_id=str(identity),
            chunk_index=i,
            raw_text=value,
            normalized_text=value,
            page_start=i + 1,
            page_end=i + 1,
            char_start=0,
            char_end=len(value),
            metadata={"tokenizer": "fixture"},
        )
        for i, value in enumerate(prose)
    )
    vectors = ((1.0, 0.0) + (0.0,) * 382, (0.0, 1.0) + (0.0,) * 382)
    return EmbeddedDocument(identity, "a" * 64, 2, chunks, vectors, EmbeddingIdentity(), "local")


def test_atomic_index_contains_metadata_provenance_vector_and_generated_fts() -> None:
    async def run() -> None:
        database = Database(load_settings())
        embedded = batch()
        owner = uuid4()
        try:
            document_id = await persist_document(
                database, embedded, filename="indexed-test.pdf", session_id=owner
            )
            assert document_id == embedded.document_id
            async with database.sessions() as session:
                document = await session.get(Document, embedded.document_id)
                assert document and document.status == "ready" and document.session_id == owner
                assert document.expires_at is not None
                metadata = await session.scalar(
                    select(EmbeddingBatch).where(EmbeddingBatch.document_id == embedded.document_id)
                )
                assert metadata and metadata.embedding_dim == 384 and metadata.chunk_count == 2
                assert metadata.embedding_model == embedded.identity.model
                assert metadata.model_revision == embedded.identity.revision
                stored = (
                    await session.scalars(
                        select(Chunk)
                        .where(Chunk.document_id == embedded.document_id)
                        .order_by(Chunk.chunk_index)
                    )
                ).all()
                assert len(stored) == 2 and stored[0].raw_text == embedded.chunks[0].raw_text
                assert stored[0].char_end == len(stored[0].raw_text)
                assert len(stored[0].embedding) == 384
                matches = (
                    await session.scalars(
                        select(Chunk.id).where(
                            Chunk.document_id == embedded.document_id,
                            Chunk.fts_tokens.op("@@")(
                                func.plainto_tsquery("english", "lexical matching")
                            ),
                        )
                    )
                ).all()
                assert matches == [stored[0].id]
                closest = await session.scalar(
                    select(Chunk.id)
                    .where(Chunk.document_id == embedded.document_id)
                    .order_by(Chunk.embedding.cosine_distance([1.0] + [0.0] * 383))
                    .limit(1)
                )
                assert closest == stored[0].id
                # Generated lexical data follows normalized text updates automatically.
                stored[1].normalized_text = "A newly updated lexical passage."
                await session.commit()
                assert (
                    await session.scalar(
                        select(Chunk.id).where(
                            Chunk.id == stored[1].id,
                            Chunk.fts_tokens.op("@@")(
                                func.plainto_tsquery("english", "newly updated")
                            ),
                        )
                    )
                    == stored[1].id
                )
        finally:
            async with database.sessions() as session, session.begin():
                await session.execute(delete(Document).where(Document.id == embedded.document_id))
            await database.close()

    asyncio.run(run())


def test_same_session_checksum_returns_existing_document_without_duplicate_rows() -> None:
    async def run() -> None:
        database = Database(load_settings())
        owner = uuid4()
        first = batch()
        duplicate = batch()
        other_session = batch()
        try:
            first_id, duplicate_id = await asyncio.gather(
                persist_document(database, first, filename="first.pdf", session_id=owner),
                persist_document(
                    database, duplicate, filename="renamed-copy.pdf", session_id=owner
                ),
            )
            other_owner_id = await persist_document(
                database, other_session, filename="same-content.pdf", session_id=uuid4()
            )
            assert duplicate_id == first_id
            canonical_id = first_id
            assert other_owner_id == other_session.document_id

            async with database.sessions() as session:
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(Document)
                        .where(Document.session_id == owner)
                    )
                    == 1
                )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(EmbeddingBatch)
                        .where(EmbeddingBatch.document_id == canonical_id)
                    )
                    == 1
                )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(Chunk)
                        .where(Chunk.document_id == canonical_id)
                    )
                    == 2
                )
                assert await session.get(Document, canonical_id) is not None
                losing_id = (
                    duplicate.document_id
                    if canonical_id == first.document_id
                    else first.document_id
                )
                assert await session.get(Document, losing_id) is None
        finally:
            async with database.sessions() as session, session.begin():
                await session.execute(
                    delete(Document).where(
                        Document.id.in_(
                            [first.document_id, duplicate.document_id, other_session.document_id]
                        )
                    )
                )
            await database.close()

    asyncio.run(run())


def test_database_failure_rolls_back_document_batch_and_all_chunks() -> None:
    async def run() -> None:
        database = Database(load_settings())
        embedded = batch()
        # Conflicting chunk UUID triggers a late insert failure after document/batch flush.
        from dataclasses import replace

        duplicated = embedded.chunks[1].model_copy(update={"id": embedded.chunks[0].id})
        broken = replace(embedded, chunks=(embedded.chunks[0], duplicated))
        try:
            with pytest.raises(SQLAlchemyError):
                await persist_document(
                    database, broken, filename="rollback-test.pdf", is_sample=True
                )
            async with database.sessions() as session:
                assert await session.get(Document, embedded.document_id) is None
                assert not (
                    await session.scalars(
                        select(EmbeddingBatch.id).where(
                            EmbeddingBatch.document_id == embedded.document_id
                        )
                    )
                ).all()
                assert not (
                    await session.scalars(
                        select(Chunk.id).where(Chunk.document_id == embedded.document_id)
                    )
                ).all()
        finally:
            await database.close()

    asyncio.run(run())


def test_concurrent_batches_are_committed_without_interleaving_or_duplicates() -> None:
    async def run() -> None:
        database = Database(load_settings())
        documents = [batch() for _ in range(3)]
        try:
            results = await asyncio.gather(
                *(
                    persist_document(database, item, filename="concurrent-test.pdf", is_sample=True)
                    for item in documents
                )
            )
            assert len(set(results)) == 3
            async with database.sessions() as session:
                count = await session.scalar(
                    select(func.count())
                    .select_from(Chunk)
                    .where(Chunk.document_id.in_([item.document_id for item in documents]))
                )
                assert count == 6
        finally:
            async with database.sessions() as session, session.begin():
                await session.execute(
                    delete(Document).where(
                        Document.id.in_([item.document_id for item in documents])
                    )
                )
            await database.close()

    asyncio.run(run())
