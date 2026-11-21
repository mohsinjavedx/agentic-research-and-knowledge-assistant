import asyncio
import json
from uuid import UUID

import httpx
import pytest

from app.providers.llm import (
    GenerationResult,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    OllamaLLM,
)
from app.schemas.answers import GroundedResponse
from app.services.retrieval.dense import RetrievedChunk


def evidence(text: str, index: int = 0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=UUID(int=index + 1),
        document_id=UUID(int=100),
        page_number=7,
        chunk_index=index,
        text=text,
        cosine_similarity=0.8,
    )


def valid_response() -> dict:
    return {
        "answer": "The benchmarks are AI2_ARC, OpenBookQA, E-EVAL, TQA, and ScienceQA.",
        "citations": [
            {
                "claim": "The benchmarks are AI2_ARC, OpenBookQA, E-EVAL, TQA, and ScienceQA.",
                "evidence_index": 0,
                "quote": "Five benchmarks: AI2_ARC, OpenBookQA, E-EVAL, TQA, ScienceQA.",
            }
        ],
        "insufficient_evidence": False,
    }


@pytest.mark.parametrize("base_url", ["http://localhost:11434", "http://localhost:11434/v1/"])
def test_native_ollama_applies_context_schema_and_output_limits(base_url: str) -> None:
    requests: list[dict] = []

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "message": {"content": json.dumps(valid_response())},
            },
        )

    async def run() -> GenerationResult:
        provider = OllamaLLM(
            base_url=base_url,
            model="llama3.2:3b",
            timeout_seconds=30,
            num_ctx=2048,
            max_output_tokens=512,
            transport=httpx.MockTransport(respond),
        )
        return await provider.generate(
            "Which five benchmarks?",
            [evidence("Five benchmarks: AI2_ARC, OpenBookQA, E-EVAL, TQA, ScienceQA.")],
        )

    result = asyncio.run(run())
    assert result.response.citations[0].evidence_index == 0
    assert requests[0]["stream"] is False
    expected_schema = GroundedResponse.model_json_schema()
    expected_schema["$defs"]["GeneratedCitation"]["properties"]["evidence_index"]["enum"] = [0]
    assert requests[0]["format"] == expected_schema
    assert requests[0]["options"] == {"num_ctx": 2048, "num_predict": 512, "temperature": 0}


def test_long_retrieval_context_keeps_whole_ranked_sources_without_changing_indices() -> None:
    sent: list[dict] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "message": {"content": json.dumps(valid_response())},
            },
        )

    first = "Five benchmarks: AI2_ARC, OpenBookQA, E-EVAL, TQA, ScienceQA."

    async def run() -> None:
        provider = OllamaLLM(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
            timeout_seconds=30,
            num_ctx=2048,
            max_output_tokens=512,
            transport=httpx.MockTransport(respond),
        )
        await provider.generate(
            "Which five benchmarks?", [evidence(first), evidence("irrelevant " * 5000, 1)]
        )

    asyncio.run(run())
    prompt = str(sent[0]["messages"][1]["content"])
    assert first in prompt
    assert 'index="0"' in prompt
    assert 'index="1"' not in prompt
    assert "irrelevant" not in prompt


@pytest.mark.parametrize("status,error", [(429, LLMRateLimitError), (500, LLMProviderError)])
def test_native_http_errors_remain_sanitized(status: int, error: type[Exception]) -> None:
    async def run() -> None:
        provider = OllamaLLM(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
            timeout_seconds=30,
            num_ctx=2048,
            max_output_tokens=512,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status, text="PRIVATE PROMPT")
            ),
        )
        with pytest.raises(error) as caught:
            await provider.generate("Question", [evidence("Source")])
        assert "PRIVATE PROMPT" not in str(caught.value)

    asyncio.run(run())


def test_native_timeout_does_not_leave_an_executor_retry_running() -> None:
    async def respond(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("PRIVATE PROMPT", request=request)

    async def run() -> None:
        provider = OllamaLLM(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
            timeout_seconds=30,
            num_ctx=2048,
            max_output_tokens=512,
            transport=httpx.MockTransport(respond),
        )
        with pytest.raises(LLMTimeoutError):
            await provider.generate("Question", [evidence("Source")])

    asyncio.run(run())


def test_token_limited_partial_json_is_not_accepted_as_a_grounded_answer() -> None:
    async def run() -> None:
        provider = OllamaLLM(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
            timeout_seconds=30,
            num_ctx=2048,
            max_output_tokens=512,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "done": True,
                        "done_reason": "length",
                        "message": {"content": json.dumps(valid_response())},
                    },
                )
            ),
        )
        with pytest.raises(LLMProviderError):
            await provider.generate("Question", [evidence("Source")])

    asyncio.run(run())


def test_cannot_cite_a_retrieved_source_excluded_from_model_context() -> None:
    draft = valid_response()
    draft["citations"][0]["evidence_index"] = 1

    async def run() -> None:
        provider = OllamaLLM(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
            timeout_seconds=30,
            num_ctx=2048,
            max_output_tokens=512,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={"done": True, "message": {"content": json.dumps(draft)}},
                )
            ),
        )
        with pytest.raises(LLMProviderError, match="outside its context"):
            await provider.generate(
                "Question", [evidence("Source"), evidence("irrelevant " * 5000, 1)]
            )

    asyncio.run(run())


@pytest.mark.parametrize(
    "body", [[], {"done": True, "message": {}}, {"done": True, "message": {"content": "PRIVATE"}}]
)
def test_malformed_native_responses_are_sanitized(body: object) -> None:
    async def run() -> None:
        provider = OllamaLLM(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
            timeout_seconds=30,
            num_ctx=2048,
            max_output_tokens=512,
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
        )
        with pytest.raises(LLMProviderError) as caught:
            await provider.generate("Question", [evidence("Source")])
        assert "PRIVATE" not in str(caught.value)

    asyncio.run(run())


def test_evidence_is_not_silently_truncated_when_even_first_chunk_cannot_fit() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        pytest.fail("Ollama must not receive a prompt outside the estimated context budget.")

    async def run() -> None:
        provider = OllamaLLM(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
            timeout_seconds=30,
            num_ctx=2048,
            max_output_tokens=512,
            transport=httpx.MockTransport(respond),
        )
        with pytest.raises(LLMProviderError, match="cannot fit"):
            await provider.generate("Question", [evidence("oversized " * 5000)])

    asyncio.run(run())


def test_total_deadline_cancels_a_request_that_never_returns() -> None:
    request_cancelled = False

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal request_cancelled
        try:
            await asyncio.Event().wait()
        finally:
            request_cancelled = True
        raise AssertionError("Unreachable")

    async def run() -> None:
        provider = OllamaLLM(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
            timeout_seconds=1,
            num_ctx=2048,
            max_output_tokens=512,
            transport=httpx.MockTransport(respond),
        )
        with pytest.raises(LLMTimeoutError):
            await provider.generate("Question", [evidence("Source")])

    asyncio.run(run())
    assert request_cancelled
