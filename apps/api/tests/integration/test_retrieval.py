import asyncio
import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api.v1.sessions import SESSION_COOKIE_NAME
from app.core.config import load_settings
from app.db.models import Document
from app.db.session import Database
from app.main import create_app
from app.providers.identity import EmbeddingIdentity
from app.services.indexing.service import persist_document
from tests.integration.test_indexing import batch

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 for real Postgres"
    ),
]


class FixedQueryEmbeddingProvider:
    identity = EmbeddingIdentity()
    kind = "local"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 383 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0] + [0.0] * 383

    def close(self) -> None:
        pass


def test_search_includes_only_samples_and_current_session_documents() -> None:
    session_id, foreign_session_id = uuid4(), uuid4()
    sample = batch()
    owned = batch()
    foreign = batch()

    async def persist_fixtures() -> None:
        database = Database(load_settings())
        try:
            await persist_document(database, sample, filename="sample.pdf", is_sample=True)
            await persist_document(database, owned, filename="owned.pdf", session_id=session_id)
            await persist_document(
                database, foreign, filename="foreign.pdf", session_id=foreign_session_id
            )
        finally:
            await database.close()

    async def cleanup() -> None:
        database = Database(load_settings())
        try:
            async with database.sessions() as session, session.begin():
                await session.execute(
                    delete(Document).where(
                        Document.id.in_(
                            [sample.document_id, owned.document_id, foreign.document_id]
                        )
                    )
                )
        finally:
            await database.close()

    asyncio.run(persist_fixtures())
    try:
        with TestClient(create_app()) as client:
            client.app.state.embedding_provider = FixedQueryEmbeddingProvider()
            client.cookies.set(SESSION_COOKIE_NAME, str(session_id), path="/api/v1")
            response = client.post("/api/v1/search", json={"query": "evidence", "top_k": 5})
            assert response.status_code == 200
            results = response.json()["results"]
            result_document_ids = {UUID(result["document_id"]) for result in results}
            assert foreign.document_id not in result_document_ids

            selected = client.post(
                "/api/v1/search",
                json={
                    "query": "evidence",
                    "document_ids": [str(sample.document_id), str(owned.document_id)],
                },
            )
            assert selected.status_code == 200
            assert {UUID(result["document_id"]) for result in selected.json()["results"]} == {
                sample.document_id,
                owned.document_id,
            }

            denied = client.post(
                "/api/v1/search",
                json={"query": "evidence", "document_ids": [str(foreign.document_id)]},
            )
            assert denied.status_code == 404

            client.cookies.clear()
            assert client.post("/api/v1/search", json={"query": "evidence"}).status_code == 401
    finally:
        asyncio.run(cleanup())
