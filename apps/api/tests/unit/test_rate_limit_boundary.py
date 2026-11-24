from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.rate_limits import QuotaDecision, RateLimitMiddleware

pytestmark = pytest.mark.rate_limits


@pytest.mark.parametrize("failure,status", [(False, 429), (True, 503)])
def test_admission_rejects_before_body_or_downstream_work(monkeypatch, failure, status):
    application = FastAPI()
    application.add_middleware(RateLimitMiddleware)
    downstream = []

    @application.post("/api/v1/documents")
    async def endpoint():
        downstream.append(1)
        raise AssertionError("Rejected upload must never reach parsing")

    enforce = AsyncMock(return_value=QuotaDecision(False, 42))
    if failure:
        enforce.side_effect = OperationalError("private database statement", {}, Exception())
    monkeypatch.setattr("app.core.rate_limits.enforce_quota", enforce)
    with TestClient(application) as client:
        client.cookies.set("session_id", str(uuid4()))
        response = client.post("/api/v1/documents", content=b"malformed-body")
    assert response.status_code == status
    assert int(response.headers["Retry-After"]) > 0
    assert downstream == []
    assert "private database" not in response.text


@pytest.mark.parametrize("failure", [TimeoutError(), ConnectionRefusedError(), OSError()])
def test_native_connection_failures_return_retryable_503(monkeypatch, failure):
    application = FastAPI()
    application.add_middleware(RateLimitMiddleware)
    enforce = AsyncMock(side_effect=failure)
    monkeypatch.setattr("app.core.rate_limits.enforce_quota", enforce)
    with TestClient(application) as client:
        response = client.post("/api/v1/answer", content=b"must-not-be-read")
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"


def test_root_path_cannot_bypass_admission(monkeypatch):
    application = FastAPI()
    application.add_middleware(RateLimitMiddleware)
    monkeypatch.setattr(
        "app.core.rate_limits.enforce_quota", AsyncMock(return_value=QuotaDecision(False, 42))
    )

    @application.post("/api/v1/answer")
    async def downstream():
        return {"incorrectly_admitted": True}

    with TestClient(application, root_path="/demo") as client:
        response = client.post("/demo/api/v1/answer")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"


def test_expiry_worker_retries_native_connection_timeout(monkeypatch):
    import asyncio

    from app.workers.expired_documents import run_expired_document_cleanup

    purge = AsyncMock(side_effect=[TimeoutError(), asyncio.CancelledError()])
    pause = AsyncMock()
    monkeypatch.setattr("app.workers.expired_documents.purge_expired_documents", purge)
    monkeypatch.setattr("app.workers.expired_documents.asyncio.sleep", pause)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_expired_document_cleanup(None))
    assert purge.await_count == 2
    pause.assert_awaited_once_with(60)
