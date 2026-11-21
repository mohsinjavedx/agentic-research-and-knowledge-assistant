import asyncio
from collections.abc import Iterator, Sequence
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.providers.llm import GenerationResult, LLMProviderError, LLMRateLimitError, LLMTimeoutError
from app.schemas.answers import GeneratedCitation, GroundedResponse
from app.services.generation.evidence import EvidencePassage
from app.services.retrieval.dense import RetrievedChunk

DOC_ID = UUID("35d86749-bf13-55ac-8008-231937b43bab")
CHUNK_ID = UUID("d16a1a1e-aed6-5af2-a59d-78a3e2be754e")


def evidence() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id=CHUNK_ID,
            document_id=DOC_ID,
            page_number=8,
            chunk_index=3,
            text="The study used five benchmarks.",
            cosine_similarity=0.8,
        )
    ]


class FakeLLM:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls = 0

    async def generate(self, question: str, chunks: Sequence[RetrievedChunk]) -> GenerationResult:
        self.calls += 1
        if self.failure:
            raise self.failure
        response = GroundedResponse(
            answer="The study used five benchmarks.",
            insufficient_evidence=False,
            citations=[
                GeneratedCitation(
                    claim="The study used five benchmarks.",
                    evidence_index=0,
                    quote="The study used five benchmarks.",
                )
            ],
        )
        return GenerationResult(
            response,
            [EvidencePassage(item, index, 0, len(item.text)) for index, item in enumerate(chunks)],
        )

    def close(self) -> None:
        pass


@pytest.fixture
def answer_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, FakeLLM, AsyncMock]]:
    database = AsyncMock()
    database.check.return_value = "0.8.2"
    monkeypatch.setattr("app.main.Database", lambda settings: database)

    async def wait_for_shutdown(database: AsyncMock) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr("app.main.run_expired_document_cleanup", wait_for_shutdown)
    monkeypatch.setattr(
        "app.api.v1.answers.visible_document_ids",
        AsyncMock(return_value=[DOC_ID]),
    )
    monkeypatch.setattr(
        "app.api.v1.answers.retrieve_evidence",
        AsyncMock(return_value=evidence()),
    )
    llm = FakeLLM()
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:secret@localhost/research",
        embedding_provider="local",
        embedding_model="BAAI/bge-small-en-v1.5",
        llm_provider="local",
    )
    with TestClient(create_app(settings)) as client:
        client.app.state.llm_provider = llm
        client.app.state.embedding_provider.embed_query = lambda query: [0.1] * 384
        client.post("/api/v1/session")
        yield client, llm, database
    database.close.assert_awaited_once()


def test_answer_endpoint_returns_verified_citations_and_retrieved_context(
    answer_client: tuple[TestClient, FakeLLM, AsyncMock],
) -> None:
    client, llm, _ = answer_client
    response = client.post("/api/v1/answer", json={"query": "What did the study evaluate?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "The study used five benchmarks."
    assert body["citations"] == [
        {
            "claim": "The study used five benchmarks.",
            "chunk_id": str(CHUNK_ID),
            "document_id": str(DOC_ID),
            "page_number": 8,
            "quote": "The study used five benchmarks.",
            "quote_start": 0,
            "quote_end": 31,
        }
    ]
    assert body["evidence"][0]["chunk_id"] == str(CHUNK_ID)
    assert body["used_evidence"][0]["retrieval_index"] == 0
    assert body["used_evidence"][0]["text"] == "The study used five benchmarks."
    assert body["insufficient_evidence"] is False
    assert body["degraded_mode"] is False
    assert llm.calls == 1
    assert "scope;dur=" in response.headers["server-timing"]
    assert "embedding;dur=" in response.headers["server-timing"]
    assert "vector_search;dur=" in response.headers["server-timing"]
    assert "generation;dur=" in response.headers["server-timing"]
    assert "total;dur=" in response.headers["server-timing"]


@pytest.mark.parametrize("failure", [LLMRateLimitError(), LLMTimeoutError()])
def test_answer_endpoint_returns_http_200_evidence_on_provider_timeout_or_rate_limit(
    answer_client: tuple[TestClient, FakeLLM, AsyncMock],
    failure: Exception,
) -> None:
    client, llm, _ = answer_client
    llm.failure = failure

    response = client.post("/api/v1/answer", json={"query": "What did the study evaluate?"})

    assert response.status_code == 200
    assert response.json()["degraded_mode"] is True
    assert response.json()["evidence"][0]["chunk_id"] == str(CHUNK_ID)


def test_answer_endpoint_requires_session_cookie(
    answer_client: tuple[TestClient, FakeLLM, AsyncMock],
) -> None:
    client, llm, _ = answer_client
    client.cookies.clear()

    response = client.post("/api/v1/answer", json={"query": "What did the study evaluate?"})

    assert response.status_code == 401
    assert llm.calls == 0


def test_answer_endpoint_surfaces_unexpected_llm_errors_safely(
    answer_client: tuple[TestClient, FakeLLM, AsyncMock],
) -> None:
    client, llm, _ = answer_client
    llm.failure = LLMProviderError("DO_NOT_RETURN_PROVIDER_DETAILS")

    response = client.post("/api/v1/answer", json={"query": "What did the study evaluate?"})

    assert response.status_code == 503
    assert "DO_NOT_RETURN_PROVIDER_DETAILS" not in response.text
