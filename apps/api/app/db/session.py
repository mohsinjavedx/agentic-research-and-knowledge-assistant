import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.embedding_compatibility import assert_embedding_compatibility
from app.workers.recovery import (
    recover_interrupted_documents,
    recover_interrupted_research_jobs,
)

SCHEMA_REVISION = "0006_rate_limit_events"


class Database:
    def __init__(self, settings: Settings) -> None:
        self.timeout = settings.db_timeout_seconds
        self.settings = settings
        self.engine = create_async_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_timeout=self.timeout,
            connect_args={"timeout": self.timeout, "command_timeout": self.timeout},
            hide_parameters=True,
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self._recovery_lock = asyncio.Lock()
        self._recovery_complete = False

    async def _ensure_recovery(self) -> None:
        if self._recovery_complete:
            return
        async with self._recovery_lock:
            if self._recovery_complete:
                return
            async with self.sessions() as session, session.begin():
                recovered = await recover_interrupted_documents(session)
                recovered_jobs = await recover_interrupted_research_jobs(session)
            self._recovery_complete = True
            logging.getLogger("research.recovery").info(
                "startup.recovery_completed",
                extra={
                    "recovered_documents": recovered,
                    "recovered_research_jobs": recovered_jobs,
                },
            )

    async def check(self) -> str:
        async with asyncio.timeout(self.timeout):
            async with self.engine.connect() as connection:
                version = await connection.scalar(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                )
                if not version:
                    raise RuntimeError("PGVECTOR_NOT_INSTALLED")
                # Exercise the actual vector type/operator, not just the extension catalog.
                distance = await connection.scalar(
                    text("SELECT '[1,0]'::vector <=> '[1,0]'::vector")
                )
                revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
                if distance != 0 or revision != SCHEMA_REVISION:
                    raise RuntimeError("DATABASE_NOT_MIGRATED")
                await assert_embedding_compatibility(connection, self.settings)
            # Release the probe connection before acquiring a transactional session;
            # concurrent startup/health requests must not exhaust the pool.
            await self._ensure_recovery()
            return str(version)

    async def close(self) -> None:
        await self.engine.dispose()
