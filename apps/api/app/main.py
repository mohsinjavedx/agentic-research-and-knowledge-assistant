import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.sessions import router as sessions_router
from app.core.config import Settings, load_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import Database
from app.providers.identity import EmbeddingCompatibilityError
from app.workers.expired_documents import run_expired_document_cleanup


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging()
    logger = logging.getLogger("research.lifecycle")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = Database(settings)
        application.state.database = database
        cleanup_task: asyncio.Task[None] | None = None
        try:
            try:
                await database.check()
                logger.info("startup.database_ready")
            except EmbeddingCompatibilityError:
                logger.error("startup.embedding_configuration_mismatch")
                raise
            except Exception:
                logger.warning(
                    "startup.database_unavailable", extra={"error_code": "DATABASE_NOT_READY"}
                )
            cleanup_task = asyncio.create_task(
                run_expired_document_cleanup(database), name="expired-document-cleanup"
            )
            yield
        finally:
            try:
                if cleanup_task is not None:
                    cleanup_task.cancel()
                    try:
                        await cleanup_task
                    except asyncio.CancelledError:
                        pass
            finally:
                await database.close()
                logger.info("shutdown.completed")

    application = FastAPI(
        title="Research & Knowledge Assistant", version="0.1.0", lifespan=lifespan
    )
    application.state.settings = settings
    application.include_router(health_router)
    application.include_router(sessions_router)
    application.include_router(documents_router)
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    return application


app = create_app()
