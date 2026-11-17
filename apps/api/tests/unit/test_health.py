import asyncio
import json
import logging
from collections.abc import Iterator
from io import StringIO
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.sessions import SESSION_COOKIE_NAME
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, AsyncMock]]:
    database = AsyncMock()
    database.check.return_value = "0.8.2"
    monkeypatch.setattr("app.main.Database", lambda settings: database)
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:secret@localhost/research",
        embedding_provider="local",
        embedding_model="BAAI/bge-small-en-v1.5",
        llm_provider="local",
    )

    async def wait_for_shutdown(database: AsyncMock) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr("app.main.run_expired_document_cleanup", wait_for_shutdown)
    application = create_app(settings)

    @application.get("/test-failure")
    async def fail() -> None:
        raise RuntimeError("DO_NOT_LOG_ME")

    with TestClient(application) as test_client:
        yield test_client, database
    database.close.assert_awaited_once()


def test_ready_and_request_correlation(client: tuple[TestClient, AsyncMock]) -> None:
    http, _ = client
    request_id = str(uuid4())
    response = http.get("/api/v1/health", headers={"X-Request-ID": request_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["db"] == "connected"
    assert response.json()["pgvector"] == "0.8.2"


def test_database_failure_and_recovery(client: tuple[TestClient, AsyncMock]) -> None:
    http, database = client
    database.check.side_effect = RuntimeError("postgresql://secret:password@private")
    response = http.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert "password" not in response.text
    assert http.get("/api/v1/health/live").status_code == 200
    database.check.side_effect = None
    assert http.get("/api/v1/health").status_code == 200


def test_cors_restricts_origins(client: tuple[TestClient, AsyncMock]) -> None:
    http, _ = client
    allowed = http.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert allowed.headers["Access-Control-Allow-Credentials"] == "true"
    denied = http.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
    assert "Access-Control-Allow-Origin" not in denied.headers


def test_invalid_request_id_is_replaced(client: tuple[TestClient, AsyncMock]) -> None:
    http, _ = client
    response = http.get("/api/v1/health/live", headers={"X-Request-ID": "arbitrary-secret"})
    assert str(UUID(response.headers["X-Request-ID"])) == response.headers["X-Request-ID"]


def test_session_endpoint_sets_private_ttl_cookie(client: tuple[TestClient, AsyncMock]) -> None:
    http, _ = client
    response = http.post("/api/v1/session")
    assert response.status_code == 204
    cookie = response.cookies[SESSION_COOKIE_NAME]
    assert str(UUID(cookie)) == cookie
    assert response.headers["set-cookie"].lower().find("httponly") >= 0
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert "max-age=86400" in response.headers["set-cookie"].lower()
    assert response.headers["cache-control"] == "no-store"


def test_errors_are_sanitized_and_correlated(client: tuple[TestClient, AsyncMock]) -> None:
    http, _ = client
    response = http.get("/test-failure")
    assert response.status_code == 500
    assert "DO_NOT_LOG_ME" not in response.text
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_request_logs_are_json_and_do_not_include_query_secrets(
    client: tuple[TestClient, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, _ = client
    stream = StringIO()
    monkeypatch.setattr(logging.getLogger("research").handlers[0], "stream", stream)
    response = http.get("/api/v1/health?token=DO_NOT_LOG_ME")
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    request_record = next(record for record in records if record["event"] == "request.completed")
    assert request_record["request_id"] == response.headers["X-Request-ID"]
    assert request_record["endpoint"] == "/api/v1/health"
    assert "DO_NOT_LOG_ME" not in json.dumps(records)
