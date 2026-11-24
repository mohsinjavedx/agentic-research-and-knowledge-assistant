import asyncio
import json
import logging
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from instructor.core.exceptions import FailedAttempt, InstructorRetryException

from app.core.config import load_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.telemetry import RequestTelemetry, begin_provider_call, telemetry_context
from app.providers.llm import LLMProviderError, OllamaLLM, OpenAICompatibleLLM
from app.services.indexing.upload import PDFUploadProcessor
from app.services.retrieval.dense import RetrievedChunk


@pytest.fixture(autouse=True)
def current_capture_logging():
    configure_logging()


def test_request_fields_are_private_and_background_time_is_separate(monkeypatch):
    configure_logging()
    stream = StringIO()
    monkeypatch.setattr(logging.getLogger("research").handlers[0], "stream", stream)
    application = FastAPI()
    application.state.settings = load_settings()
    application.add_middleware(RequestContextMiddleware)
    owner, request_id = uuid4(), str(uuid4())

    async def background():
        await asyncio.sleep(0.05)
        call = begin_provider_call("hosted")
        await asyncio.to_thread(call.complete, 123)

    @application.get("/jobs/{job_id}")
    async def endpoint(job_id: str, tasks: BackgroundTasks):
        tasks.add_task(background)
        return JSONResponse({"ok": True})

    with TestClient(application) as client:
        client.cookies.set("session_id", str(owner))
        client.get("/jobs/PRIVATE_PATH?key=PRIVATE_QUERY", headers={"X-Request-ID": request_id})
    raw = stream.getvalue()
    row = next(
        json.loads(line)
        for line in raw.splitlines()
        if json.loads(line)["event"] == "request.completed"
    )
    assert row["request_id"] == request_id
    assert len(row["session_id"]) == 64
    assert row["endpoint"] == "/jobs/{job_id}"
    assert row["tokens_used"] == 123
    assert row["provider"] == "hosted"
    assert row["error_code"] is None
    assert row["background_ms"] >= 45
    assert row["latency_ms"] < row["total_ms"] - 40
    assert all(secret not in raw for secret in (str(owner), "PRIVATE_PATH", "PRIVATE_QUERY"))


def test_usage_is_actual_unknown_or_zero_and_thread_safe():
    telemetry = RequestTelemetry(session_id=None)
    token = telemetry_context.set(telemetry)
    try:
        assert telemetry.snapshot()["tokens_used"] == 0
        first = begin_provider_call("hosted")
        first.complete(17)
        assert telemetry.snapshot()["tokens_used"] == 17
        second = begin_provider_call("api")
        assert telemetry.snapshot()["tokens_used"] is None
        second.complete(11)
        assert telemetry.snapshot()["tokens_used"] == 28
        begin_provider_call("local").complete(True)  # Invalid usage must not invent a count.
        assert telemetry.snapshot()["tokens_used"] is None
    finally:
        telemetry_context.reset(token)


def test_hosted_usage_comes_from_sdk_completion_and_survives_to_thread(monkeypatch):
    provider = OpenAICompatibleLLM(
        base_url="https://example.test/v1", api_key="test-only", model="test", timeout_seconds=2
    )
    from app.schemas.answers import GroundedResponse

    draft = GroundedResponse(
        answer="Insufficient evidence.", citations=[], insufficient_evidence=True
    )
    create = Mock(return_value=(draft, SimpleNamespace(usage=SimpleNamespace(total_tokens=321))))
    monkeypatch.setattr(provider._client, "create_with_completion", create)
    telemetry = RequestTelemetry(session_id=None)
    token = telemetry_context.set(telemetry)
    try:
        asyncio.run(
            provider.generate(
                "Question?",
                [
                    RetrievedChunk(
                        UUID(int=1), UUID(int=2), 1, 0, "A complete source sentence.", 0.8
                    )
                ],
            )
        )
        assert telemetry.snapshot()["tokens_used"] == 321
        assert telemetry.snapshot()["provider"] == "hosted"
    finally:
        telemetry_context.reset(token)
        provider.close()


def test_upload_executor_carries_request_context(monkeypatch):
    from app.core.logging import request_id_context

    seen = []

    def prepare(*args):
        seen.append(request_id_context.get())
        begin_provider_call("local").complete(19)
        return "prepared"

    monkeypatch.setattr("app.services.indexing.upload._prepare", prepare)
    telemetry = RequestTelemetry(session_id=None)
    usage_token = telemetry_context.set(telemetry)
    id_token = request_id_context.set("correlated-worker")

    async def run():
        processor = PDFUploadProcessor()
        try:
            assert (
                await processor.prepare(None, None, None, "x.pdf", "application/pdf") == "prepared"
            )
        finally:
            processor.close()

    try:
        asyncio.run(run())
        assert seen == ["correlated-worker"]
        assert telemetry.snapshot()["tokens_used"] == 19
    finally:
        telemetry_context.reset(usage_token)
        request_id_context.reset(id_token)


def test_sdk_logs_cannot_echo_credentials_or_document_text(monkeypatch, capsys):
    configure_logging()
    stream = StringIO()
    monkeypatch.setattr(logging.getLogger("research").handlers[0], "stream", stream)
    for name in ("instructor.v2.core.retry", "openai._base_client", "httpx", "httpcore.http11"):
        logging.getLogger(name).error("PRIVATE_API_KEY PRIVATE_PDF_CONTENT")
    output = capsys.readouterr()
    assert "PRIVATE_API_KEY" not in output.out + output.err + stream.getvalue()


@pytest.mark.parametrize("reported,expected", [(None, None), (0, 0), (42, 42)])
def test_failed_hosted_calls_do_not_invent_usage_from_instructor_accumulator(
    monkeypatch, reported, expected
):
    provider = OpenAICompatibleLLM(
        base_url="https://example.test/v1", api_key="test-only", model="test", timeout_seconds=2
    )
    completion = SimpleNamespace(
        usage=None if reported is None else SimpleNamespace(total_tokens=reported)
    )
    failure = InstructorRetryException(
        "private provider error",
        n_attempts=1,
        total_usage=SimpleNamespace(total_tokens=0),
        failed_attempts=[FailedAttempt(1, ValueError("invalid JSON"), completion)],
    )
    monkeypatch.setattr(provider._client, "create_with_completion", Mock(side_effect=failure))
    telemetry = RequestTelemetry(session_id=None)
    token = telemetry_context.set(telemetry)
    try:
        with pytest.raises(LLMProviderError):
            asyncio.run(
                provider.generate(
                    "Question?",
                    [
                        RetrievedChunk(
                            UUID(int=1), UUID(int=2), 1, 0, "A complete source sentence.", 0.8
                        )
                    ],
                )
            )
        assert telemetry.snapshot()["tokens_used"] == expected
    finally:
        telemetry_context.reset(token)
        provider.close()


@pytest.mark.parametrize("prompt,answer,expected", [(10, 4, 14), (None, None, None), (-1, 5, None)])
def test_ollama_only_reports_valid_actual_counts(prompt, answer, expected):
    draft = {"answer": "No evidence.", "citations": [], "insufficient_evidence": True}
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "done": True,
                "message": {"content": json.dumps(draft)},
                "prompt_eval_count": prompt,
                "eval_count": answer,
            },
        )
    )
    provider = OllamaLLM(
        base_url="http://localhost:11434",
        model="test",
        timeout_seconds=2,
        num_ctx=2048,
        max_output_tokens=512,
        transport=transport,
    )
    telemetry = RequestTelemetry(session_id=None)
    token = telemetry_context.set(telemetry)
    try:
        asyncio.run(
            provider.generate(
                "Question?",
                [
                    RetrievedChunk(
                        UUID(int=1), UUID(int=2), 1, 0, "A complete source sentence.", 0.8
                    )
                ],
            )
        )
        assert telemetry.snapshot()["tokens_used"] == expected
    finally:
        telemetry_context.reset(token)
