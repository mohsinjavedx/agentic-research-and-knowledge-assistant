import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.config import load_settings
from app.db.models import Document
from app.db.session import Database
from app.providers.identity import EmbeddingIdentity
from app.services.indexing.service import persist_document
from app.services.research.tools import ResearchToolError, ResearchToolRegistry, ResearchTools
from tests.integration.test_indexing import batch

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"),
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


def test_research_tools_are_read_only_and_confined_to_visible_documents() -> None:
    async def run() -> None:
        database = Database(load_settings())
        session_id = uuid4()
        sample, owned, foreign = batch(), batch(), batch()
        sample_id, owned_id, foreign_id = sample.document_id, owned.document_id, foreign.document_id
        try:
            await persist_document(database, sample, filename="research-sample.pdf", is_sample=True)
            await persist_document(
                database, owned, filename="research-owned.pdf", session_id=session_id
            )
            await persist_document(
                database, foreign, filename="research-foreign.pdf", session_id=uuid4()
            )
            tools = ResearchTools(
                database,
                FixedQueryEmbeddingProvider(),
                load_settings(),
                session_id=session_id,
                allowed_doc_ids=[sample_id, owned_id],
            )
            registry = ResearchToolRegistry(tools)

            outline = await registry.invoke("get_document_outline", {"doc_id": str(sample_id)})
            assert outline.document_id == sample_id
            assert outline.filename == "research-sample.pdf"
            assert [(item.heading, item.page_number) for item in outline.sections] == [
                ("Page 1", 1),
                ("Page 2", 2),
            ]

            results = await registry.invoke(
                "search_documents",
                {
                    "query": "lexical matching",
                    "doc_ids": [str(sample_id), str(owned_id)],
                    "top_k": 5,
                },
            )
            assert {item.document_id for item in results} == {sample_id, owned_id}

            comparison = await registry.invoke(
                "compare_sections",
                {
                    "doc_a_id": str(sample_id),
                    "doc_b_id": str(owned_id),
                    "topic": "lexical matching",
                },
            )
            assert comparison.doc_a_id == sample_id
            assert comparison.doc_b_id == owned_id
            assert {item.document_id for item in comparison.evidence_a} <= {sample_id}
            assert {item.document_id for item in comparison.evidence_b} <= {owned_id}

            with pytest.raises(ResearchToolError, match="DOCUMENT_OUTSIDE_RESEARCH_SCOPE"):
                await registry.invoke("get_document_outline", {"doc_id": str(foreign_id)})
        finally:
            async with database.sessions() as session, session.begin():
                await session.execute(
                    delete(Document).where(Document.id.in_([sample_id, owned_id, foreign_id]))
                )
            await database.close()

    asyncio.run(run())
