import logging
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.core.config import Settings
from app.db.session import Database

router = APIRouter(prefix="/api/v1", tags=["health"])
logger = logging.getLogger("research.health")


class HealthResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    db: Literal["connected", "unavailable"]
    pgvector: str | None
    embedding_model: str
    llm_provider: str
    model_configured: bool = True


@router.get("/health/live")
async def liveness(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "alive"}


@router.get("/health", response_model=HealthResponse)
async def readiness(request: Request, response: Response) -> HealthResponse:
    settings: Settings = request.app.state.settings
    database: Database = request.app.state.database
    response.headers["Cache-Control"] = "no-store"
    try:
        version = await database.check()
    except Exception:
        logger.warning("database.unavailable", extra={"error_code": "DATABASE_NOT_READY"})
        response.status_code = 503
        return HealthResponse(
            status="not_ready",
            db="unavailable",
            pgvector=None,
            embedding_model=settings.embedding_model,
            llm_provider=settings.llm_provider,
        )
    return HealthResponse(
        status="ready",
        db="connected",
        pgvector=version,
        embedding_model=settings.embedding_model,
        llm_provider=settings.llm_provider,
    )
