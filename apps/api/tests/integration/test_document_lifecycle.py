import asyncio
import os
import time
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.api.v1.sessions import SESSION_COOKIE_NAME
from app.core.config import load_settings
from app.db.models import Chunk, Document, EmbeddingBatch
from app.db.session import Database
from app.main import create_app
from app.services.indexing.service import persist_document
from app.workers.expired_documents import cleanup_expired_documents
from tests.integration.test_indexing import batch

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 for real Postgres"
    ),
]


def test_session_delete_is_owner_scoped_and_cascades_all_index_rows() -> None:
    embedded = batch()

    async def persist(owner: UUID) -> None:
        database = Database(load_settings())
        try:
            await persist_document(
                database,
                embedded,
                filename="delete-test.pdf",
                session_id=owner,
            )
        finally:
            await database.close()

    async def count_rows() -> tuple[int, int, int]:
        database = Database(load_settings())
        try:
            async with database.sessions() as session:
                return (
                    await session.scalar(
                        select(func.count())
                        .select_from(Document)
                        .where(Document.id == embedded.document_id)
                    ),
                    await session.scalar(
                        select(func.count())
                        .select_from(EmbeddingBatch)
                        .where(EmbeddingBatch.document_id == embedded.document_id)
                    ),
                    await session.scalar(
                        select(func.count())
                        .select_from(Chunk)
                        .where(Chunk.document_id == embedded.document_id)
                    ),
                )
        finally:
            await database.close()

    try:
        with TestClient(create_app()) as client:
            assert client.post("/api/v1/session").status_code == 204
            owner = UUID(client.cookies.get(SESSION_COOKIE_NAME))
            asyncio.run(persist(owner))

            client.cookies.clear()
            assert client.delete(f"/api/v1/documents/{embedded.document_id}").status_code == 401
            client.cookies.set(SESSION_COOKIE_NAME, str(uuid4()), path="/api/v1")
            assert client.delete(f"/api/v1/documents/{embedded.document_id}").status_code == 404

            assert asyncio.run(count_rows()) == (1, 1, 2)
            client.cookies.set(SESSION_COOKIE_NAME, str(owner), path="/api/v1")
            assert client.delete(f"/api/v1/documents/{embedded.document_id}").status_code == 204
            assert asyncio.run(count_rows()) == (0, 0, 0)
    finally:

        async def cleanup() -> None:
            database = Database(load_settings())
            try:
                async with database.sessions() as session, session.begin():
                    await session.execute(
                        delete(Document).where(Document.id == embedded.document_id)
                    )
            finally:
                await database.close()

        asyncio.run(cleanup())


def test_cleanup_removes_only_strictly_expired_session_documents() -> None:
    async def run() -> None:
        database = Database(load_settings())
        identities = [uuid4(), uuid4(), uuid4()]
        try:
            async with database.sessions() as session, session.begin():
                now = await session.scalar(select(func.now()))
                session.add_all(
                    [
                        Document(
                            id=identities[0],
                            session_id=uuid4(),
                            filename="expired.pdf",
                            checksum="1" * 64,
                            status="ready",
                            expires_at=now - timedelta(seconds=1),
                        ),
                        Document(
                            id=identities[1],
                            session_id=uuid4(),
                            filename="at-boundary.pdf",
                            checksum="2" * 64,
                            status="ready",
                            expires_at=now,
                        ),
                        Document(
                            id=identities[2],
                            is_sample=True,
                            filename="sample.pdf",
                            checksum="3" * 64,
                            status="ready",
                            expires_at=now - timedelta(seconds=1),
                        ),
                    ]
                )
                await session.flush()
                assert await cleanup_expired_documents(session) == 1
                assert await session.get(Document, identities[0]) is None
                assert await session.get(Document, identities[1]) is not None
                assert await session.get(Document, identities[2]) is not None
        finally:
            async with database.sessions() as session, session.begin():
                await session.execute(delete(Document).where(Document.id.in_(identities)))
            await database.close()

    asyncio.run(run())


def test_api_lifespan_runs_expiry_cleanup_automatically() -> None:
    identity = uuid4()

    async def seed_expired_document() -> None:
        database = Database(load_settings())
        try:
            async with database.sessions() as session, session.begin():
                now = await session.scalar(select(func.now()))
                session.add(
                    Document(
                        id=identity,
                        session_id=uuid4(),
                        filename="automatic-cleanup.pdf",
                        checksum="4" * 64,
                        status="ready",
                        expires_at=now - timedelta(seconds=1),
                    )
                )
        finally:
            await database.close()

    async def exists() -> bool:
        database = Database(load_settings())
        try:
            async with database.sessions() as session:
                return (
                    await session.scalar(select(Document.id).where(Document.id == identity))
                ) is not None
        finally:
            await database.close()

    async def remove_if_present() -> None:
        database = Database(load_settings())
        try:
            async with database.sessions() as session, session.begin():
                await session.execute(delete(Document).where(Document.id == identity))
        finally:
            await database.close()

    asyncio.run(seed_expired_document())
    try:
        with TestClient(create_app()):
            for _ in range(40):
                if not asyncio.run(exists()):
                    break
                time.sleep(0.05)
            assert asyncio.run(exists()) is False
    finally:
        asyncio.run(remove_if_present())
