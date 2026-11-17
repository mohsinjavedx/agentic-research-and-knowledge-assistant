import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router
from app.core.config import Settings, load_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import Database
from app.providers.identity import EmbeddingCompatibilityError


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging()
    logger = logging.getLogger("research.lifecycle")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = Database(settings)
        application.state.database = database
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
            yield
        finally:
            await database.close()
            logger.info("shutdown.completed")

    application = FastAPI(
        title="Research & Knowledge Assistant", version="0.1.0", lifespan=lifespan
    )
    application.state.settings = settings
    application.include_router(router)
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
