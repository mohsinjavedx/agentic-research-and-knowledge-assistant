import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings

SCHEMA_REVISION = "0001_pgvector"


class Database:
    def __init__(self, settings: Settings) -> None:
        self.timeout = settings.db_timeout_seconds
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
                return str(version)

    async def close(self) -> None:
        await self.engine.dispose()
