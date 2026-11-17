import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.embedding_compatibility import assert_embedding_compatibility
from app.main import create_app
from app.providers.identity import EmbeddingCompatibilityError


def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:secret@localhost/test",
        embedding_provider="local",
        embedding_model="BAAI/bge-small-en-v1.5",
        llm_provider="local",
    )


@pytest.mark.parametrize(
    "column_type,mismatch", [("vector(768)", None), (None, None), ("vector(384)", True)]
)
def test_schema_or_model_mismatch_is_rejected(
    column_type: str | None, mismatch: bool | None
) -> None:
    connection = AsyncMock()
    connection.scalar.side_effect = [column_type, mismatch]
    with pytest.raises(EmbeddingCompatibilityError) as caught:
        asyncio.run(assert_embedding_compatibility(connection, settings()))
    assert "secret" not in str(caught.value)


def test_compatible_empty_or_populated_index_is_accepted() -> None:
    connection = AsyncMock()
    connection.scalar.side_effect = ["vector(384)", None]
    asyncio.run(assert_embedding_compatibility(connection, settings()))


def test_model_mismatch_fails_startup_and_closes_database(monkeypatch: pytest.MonkeyPatch) -> None:
    database = AsyncMock()
    database.check.side_effect = EmbeddingCompatibilityError("EMBEDDING_MODEL_MISMATCH")
    monkeypatch.setattr("app.main.Database", lambda config: database)
    with pytest.raises(EmbeddingCompatibilityError):
        with TestClient(create_app(settings())):
            pass
    database.close.assert_awaited_once()


def test_ordinary_database_outage_keeps_liveness_available(monkeypatch: pytest.MonkeyPatch) -> None:
    database = AsyncMock()
    database.check.side_effect = OSError("database offline")
    monkeypatch.setattr("app.main.Database", lambda config: database)

    async def wait_for_shutdown(database: AsyncMock) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr("app.main.run_expired_document_cleanup", wait_for_shutdown)
    with TestClient(create_app(settings())) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health").status_code == 503


def test_unsupported_model_cannot_start_against_this_index() -> None:
    config = settings().model_copy(update={"embedding_model": "different-model"})
    connection = AsyncMock()
    with pytest.raises(EmbeddingCompatibilityError):
        asyncio.run(assert_embedding_compatibility(connection, config))
