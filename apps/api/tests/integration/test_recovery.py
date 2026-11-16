import asyncio
import os
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import load_settings
from app.db.models import Document
from app.db.session import Database
from app.main import create_app
from app.workers.recovery import recover_interrupted_documents

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 for real Postgres"
    ),
]


def row(
    *, identity: UUID, status: str, updated_at: object, error_code: str | None = None
) -> Document:
    return Document(
        id=identity,
        is_sample=True,
        filename=f"recovery-test-{identity}.pdf",
        checksum="0" * 64,
        status=status,
        updated_at=updated_at,
        error_code=error_code,
    )


def test_recovery_strict_cutoff_terminal_states_and_idempotence() -> None:
    async def run() -> None:
        database = Database(load_settings())
        try:
            async with database.sessions() as session:
                await session.begin()
                try:
                    now = await session.scalar(select(func.now()))
                    cases = [
                        ("queued", 7, None),
                        ("processing", 6, None),
                        ("queued", 5, None),
                        ("processing", 4, None),
                        ("ready", 9, None),
                        ("failed", 9, "ORIGINAL_ERROR"),
                    ]
                    identities = [uuid4() for _ in cases]
                    for identity, (status, minutes, error) in zip(identities, cases, strict=True):
                        session.add(
                            row(
                                identity=identity,
                                status=status,
                                updated_at=now - timedelta(minutes=minutes),
                                error_code=error,
                            )
                        )
                    await session.flush()
                    await recover_interrupted_documents(session)
                    values = {
                        identity: (status, error)
                        for identity, status, error in (
                            await session.execute(
                                select(Document.id, Document.status, Document.error_code).where(
                                    Document.id.in_(identities)
                                )
                            )
                        )
                    }
                    assert values[identities[0]] == ("failed", "INTERRUPTED_BY_RESTART")
                    assert values[identities[1]] == ("failed", "INTERRUPTED_BY_RESTART")
                    assert values[identities[2]] == ("queued", None)  # Exactly five minutes.
                    assert values[identities[3]] == ("processing", None)
                    assert values[identities[4]] == ("ready", None)
                    assert values[identities[5]] == ("failed", "ORIGINAL_ERROR")
                    assert await recover_interrupted_documents(session) == 0
                finally:
                    # Roll back every change in this transactional boundary test.
                    await session.rollback()
        finally:
            await database.close()

    asyncio.run(run())


async def seed(identity: UUID) -> None:
    database = Database(load_settings())
    try:
        async with database.sessions() as session, session.begin():
            now = await session.scalar(select(func.now()))
            session.add(
                row(identity=identity, status="processing", updated_at=now - timedelta(minutes=6))
            )
    finally:
        await database.close()


async def inspect_and_delete(identity: UUID) -> tuple[str, str | None]:
    database = Database(load_settings())
    try:
        async with database.sessions() as session, session.begin():
            result = (
                await session.execute(
                    select(Document.status, Document.error_code).where(Document.id == identity)
                )
            ).one()
            await session.execute(delete(Document).where(Document.id == identity))
            return result[0], result[1]
    finally:
        await database.close()


def test_lifespan_recovery_commits_failed_state_to_postgres() -> None:
    identity = uuid4()
    asyncio.run(seed(identity))
    try:
        with TestClient(create_app()) as client:
            assert client.get("/api/v1/health").status_code == 200
    finally:
        result = asyncio.run(inspect_and_delete(identity))
    assert result == ("failed", "INTERRUPTED_BY_RESTART")


def test_health_checks_do_not_repeatedly_fail_jobs_after_startup() -> None:
    async def run() -> None:
        identity = uuid4()
        database = Database(load_settings())
        try:
            await database.check()  # Completes this process's recovery before the row exists.
            async with database.sessions() as session, session.begin():
                now = await session.scalar(select(func.now()))
                session.add(
                    row(identity=identity, status="queued", updated_at=now - timedelta(minutes=6))
                )
            await database.check()
            async with database.sessions() as session:
                assert (
                    await session.scalar(select(Document.status).where(Document.id == identity))
                    == "queued"
                )
            restarted = Database(load_settings())
            try:
                await restarted.check()
            finally:
                await restarted.close()
            async with database.sessions() as session:
                assert (
                    await session.scalar(select(Document.error_code).where(Document.id == identity))
                    == "INTERRUPTED_BY_RESTART"
                )
        finally:
            async with database.sessions() as session, session.begin():
                await session.execute(delete(Document).where(Document.id == identity))
            await database.close()

    asyncio.run(run())


def test_concurrent_readiness_checks_recover_once_without_pool_starvation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def recover(session: AsyncSession) -> int:
        nonlocal calls
        calls += 1
        return await recover_interrupted_documents(session)

    monkeypatch.setattr("app.db.session.recover_interrupted_documents", recover)

    async def run() -> None:
        database = Database(load_settings())
        try:
            results = await asyncio.gather(*(database.check() for _ in range(12)))
            assert all(results)
            assert calls == 1
        finally:
            await database.close()

    asyncio.run(run())
