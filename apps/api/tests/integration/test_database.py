import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import load_settings
from app.db.session import Database
from app.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 for real Postgres"
    ),
]


def test_ten_consecutive_readiness_checks() -> None:
    with TestClient(create_app()) as client:
        for _ in range(10):
            response = client.get("/api/v1/health")
            assert response.status_code == 200, response.text
            assert response.json()["db"] == "connected"
            assert response.json()["pgvector"]


def test_database_pool_and_vector_operations() -> None:
    async def check() -> None:
        database = Database(load_settings())
        try:
            assert await database.check()
            async with database.sessions() as session:
                result = await session.scalar(
                    text("SELECT '[1,0,0]'::vector <-> '[0,1,0]'::vector")
                )
                assert float(result) == pytest.approx(2**0.5)
        finally:
            await database.close()

    asyncio.run(check())
