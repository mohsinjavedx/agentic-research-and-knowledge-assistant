import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, update

from app.core.config import load_settings
from app.core.identity import request_identity
from app.core.rate_limits import RateLimitMiddleware, consume_quota
from app.db.models import RateLimitEvent
from app.db.session import Database
from app.workers.expired_documents import cleanup_expired_rate_limits

pytestmark = [
    pytest.mark.integration,
    pytest.mark.rate_limits,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"),
]


def settings():
    return load_settings().model_copy(
        update={"privacy_hash_key": SecretStr(uuid4().hex + uuid4().hex)}
    )


def test_atomic_admission_survives_new_database_and_window_expiry():
    async def run():
        config = settings()
        identity = request_identity(config, "203.0.113.1", uuid4())
        database = Database(config)
        restarted = None
        try:
            decisions = await asyncio.gather(
                *[
                    consume_quota(database, identity, "chat", limit=5, window_seconds=60)
                    for _ in range(12)
                ]
            )
            assert sum(row.allowed for row in decisions) == 5
            assert all(1 <= row.retry_after <= 60 for row in decisions if not row.allowed)
            await database.close()
            restarted = Database(config)
            denied = await consume_quota(restarted, identity, "chat", limit=5, window_seconds=60)
            assert not denied.allowed
            async with restarted.sessions() as session, session.begin():
                await session.execute(
                    update(RateLimitEvent)
                    .where(RateLimitEvent.ip_hash == identity.ip_hash)
                    .values(created_at=RateLimitEvent.created_at - timedelta(seconds=61))
                )
            assert (
                await consume_quota(restarted, identity, "chat", limit=5, window_seconds=60)
            ).allowed
        finally:
            final = restarted or database
            async with final.sessions() as session, session.begin():
                await session.execute(
                    delete(RateLimitEvent).where(RateLimitEvent.ip_hash == identity.ip_hash)
                )
            await final.close()

    asyncio.run(run())


def test_session_budget_follows_changed_ip_and_cleanup_keeps_active_events():
    async def run():
        config = settings()
        owner = uuid4()
        first = request_identity(config, "192.0.2.1", owner)
        changed = request_identity(config, "192.0.2.2", owner)
        database = Database(config)
        try:
            assert (
                await consume_quota(database, first, "chat", limit=1, window_seconds=60)
            ).allowed
            assert not (
                await consume_quota(database, changed, "chat", limit=1, window_seconds=60)
            ).allowed
            async with database.sessions() as session, session.begin():
                session.add(
                    RateLimitEvent(
                        action="upload",
                        ip_hash=first.ip_hash,
                        session_hash=first.session_hash,
                        created_at=datetime.now(UTC) - timedelta(hours=2),
                    )
                )
            async with database.sessions() as session, session.begin():
                await cleanup_expired_rate_limits(session)
            assert not (
                await consume_quota(database, changed, "chat", limit=1, window_seconds=60)
            ).allowed
        finally:
            async with database.sessions() as session, session.begin():
                await session.execute(
                    delete(RateLimitEvent).where(RateLimitEvent.session_hash == first.session_hash)
                )
            await database.close()

    asyncio.run(run())


@pytest.mark.parametrize("path,quota", [("/answer", 5), ("/research", 2), ("/documents", 3)])
def test_http_limits_persist_across_apps_ignore_forged_headers_and_new_cookies(path, quota):
    config = settings()
    owner = uuid4()
    identity = request_identity(config, "testclient", owner)
    calls = []

    def app():
        database = Database(config)

        @asynccontextmanager
        async def lifespan(application):
            yield
            await database.close()

        application = FastAPI(lifespan=lifespan)
        application.state.database = database
        application.state.settings = config

        @application.post("/api/v1" + path)
        async def downstream():
            calls.append(1)
            return {"ok": True}

        application.add_middleware(RateLimitMiddleware)
        return application

    try:
        with TestClient(app()) as client:
            client.cookies.set("session_id", str(owner))
            for _ in range(quota):
                assert client.post("/api/v1" + path).status_code == 200
        with TestClient(app()) as client:
            client.cookies.set("session_id", str(uuid4()))
            response = client.post("/api/v1" + path, headers={"X-Forwarded-For": "192.0.2.99"})
            assert response.status_code == 429
            assert int(response.headers["Retry-After"]) > 0
        assert len(calls) == quota
    finally:

        async def cleanup():
            database = Database(config)
            try:
                async with database.sessions() as session, session.begin():
                    await session.execute(
                        delete(RateLimitEvent).where(RateLimitEvent.ip_hash == identity.ip_hash)
                    )
            finally:
                await database.close()

        asyncio.run(cleanup())
