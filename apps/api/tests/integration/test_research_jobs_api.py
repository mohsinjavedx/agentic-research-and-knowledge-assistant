import asyncio
import os
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.api.v1.sessions import SESSION_COOKIE_NAME
from app.core.config import load_settings
from app.db.models import Document, ResearchJob
from app.db.session import Database
from app.main import create_app
from app.providers.identity import EmbeddingIdentity
from app.providers.llm import GenerationResult
from app.schemas.answers import GeneratedCitation, GroundedResponse
from app.services.generation.evidence import EvidencePassage
from app.services.indexing.service import persist_document
from app.services.retrieval.dense import RetrievedChunk
from app.workers.recovery import recover_interrupted_research_jobs
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


class FixedGroundedLLM:
    async def generate(self, question: str, evidence: list[RetrievedChunk]) -> GenerationResult:
        source = evidence[0]
        claim = source.text
        response = GroundedResponse(
            answer=claim,
            citations=[
                GeneratedCitation(
                    claim=claim,
                    evidence_index=0,
                    quote=claim,
                )
            ],
            insufficient_evidence=False,
        )
        return GenerationResult(
            response=response,
            passages=[EvidencePassage(source=source, retrieval_index=0, start=0, end=len(claim))],
        )

    def close(self) -> None:
        pass


def test_research_job_runs_persists_progress_and_enforces_session_ownership() -> None:
    owner_session = uuid4()
    sample, owned, foreign = batch(), batch(), batch()
    sample_id, owned_id, foreign_id = sample.document_id, owned.document_id, foreign.document_id

    async def seed_documents() -> None:
        database = Database(load_settings())
        try:
            await persist_document(database, sample, filename="phase6-sample.pdf", is_sample=True)
            await persist_document(
                database, owned, filename="phase6-owned.pdf", session_id=owner_session
            )
            await persist_document(
                database, foreign, filename="phase6-foreign.pdf", session_id=uuid4()
            )
        finally:
            await database.close()

    async def cleanup() -> None:
        database = Database(load_settings())
        try:
            async with database.sessions() as session, session.begin():
                await session.execute(
                    delete(ResearchJob).where(ResearchJob.session_id == owner_session)
                )
                await session.execute(
                    delete(Document).where(Document.id.in_([sample_id, owned_id, foreign_id]))
                )
        finally:
            await database.close()

    asyncio.run(seed_documents())
    try:
        with TestClient(create_app()) as client:
            client.app.state.embedding_provider = FixedQueryEmbeddingProvider()
            client.app.state.llm_provider = FixedGroundedLLM()
            client.cookies.set(SESSION_COOKIE_NAME, str(owner_session), path="/api/v1")
            submitted = client.post(
                "/api/v1/research",
                json={
                    "query": (
                        "Which five benchmarks are used to evaluate the educational "
                        "question-answering system?"
                    ),
                    "document_ids": [str(sample_id), str(owned_id)],
                    "top_k": 5,
                },
            )
            assert submitted.status_code == 202
            job_id = UUID(submitted.json()["job_id"])

            completed = client.get(f"/api/v1/research/{job_id}")
            assert completed.status_code == 200
            body = completed.json()
            assert body["status"] == "completed"
            assert body["iterations"] == 1
            assert body["tool_calls_count"] == 2
            assert [call["name"] for call in body["tool_calls"]] == [
                "search_documents",
                "compare_sections",
            ]
            assert [step["name"] for step in body["steps"]] == [
                "plan",
                "execute_tools",
                "assess_sufficiency",
                "synthesize",
                "verify_citations",
            ]
            assert body["report"]["citations"]
            assert {item["document_id"] for item in body["evidence"]} == {
                str(sample_id),
                str(owned_id),
            }
            rejected = client.post(
                "/api/v1/research",
                json={
                    "query": "Compare these sources",
                    "document_ids": [str(sample_id), str(foreign_id)],
                },
            )
            assert rejected.status_code == 404

            client.cookies.set(SESSION_COOKIE_NAME, str(uuid4()), path="/api/v1")
            assert client.get(f"/api/v1/research/{job_id}").status_code == 404
            client.cookies.clear()
            assert client.get(f"/api/v1/research/{job_id}").status_code == 401
    finally:
        asyncio.run(cleanup())


def test_session_bootstrap_does_not_replace_an_existing_session() -> None:
    with TestClient(create_app()) as client:
        assert client.post("/api/v1/session").status_code == 204
        first = client.cookies.get(SESSION_COOKIE_NAME)
        assert first
        assert client.post("/api/v1/session").status_code == 204
        assert client.cookies.get(SESSION_COOKIE_NAME) == first


def test_stale_research_jobs_are_marked_failed_on_recovery() -> None:
    async def run() -> None:
        database = Database(load_settings())
        identities = [uuid4(), uuid4(), uuid4()]
        try:
            async with database.sessions() as session, session.begin():
                now = await session.scalar(select(func.now()))
                session.add_all(
                    [
                        ResearchJob(
                            id=identities[0],
                            session_id=uuid4(),
                            query="stale queued job",
                            document_ids=[],
                            status="queued",
                            created_at=now - timedelta(minutes=10),
                            updated_at=now - timedelta(minutes=10),
                        ),
                        ResearchJob(
                            id=identities[1],
                            session_id=uuid4(),
                            query="stale running job",
                            document_ids=[],
                            status="running",
                            created_at=now - timedelta(minutes=10),
                            updated_at=now - timedelta(minutes=10),
                        ),
                        ResearchJob(
                            id=identities[2],
                            session_id=uuid4(),
                            query="completed job",
                            document_ids=[],
                            status="completed",
                            created_at=now - timedelta(minutes=10),
                            updated_at=now - timedelta(minutes=10),
                        ),
                    ]
                )
                await session.flush()
                assert await recover_interrupted_research_jobs(session) == 2
                assert (await session.get(ResearchJob, identities[0])).error_code == (
                    "INTERRUPTED_BY_RESTART"
                )
                assert (await session.get(ResearchJob, identities[1])).status == "failed"
                assert (await session.get(ResearchJob, identities[2])).status == "completed"
        finally:
            async with database.sessions() as session, session.begin():
                await session.execute(delete(ResearchJob).where(ResearchJob.id.in_(identities)))
            await database.close()

    asyncio.run(run())
