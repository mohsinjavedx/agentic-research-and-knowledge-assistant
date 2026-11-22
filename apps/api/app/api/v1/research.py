"""Session-scoped asynchronous research jobs."""

import logging
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.sessions import require_session_id
from app.core.config import Settings
from app.db.models import ResearchJob
from app.db.session import Database
from app.providers.embeddings import EmbeddingProvider, EmbeddingProviderError
from app.providers.llm import LLMProvider, LLMProviderError
from app.schemas.research import (
    ResearchJobResponse,
    ResearchReport,
    ResearchRequest,
    ResearchStatus,
    ResearchStep,
    ResearchStepStatus,
    ResearchToolCall,
)
from app.schemas.retrieval import SearchResult
from app.services.research.graph import (
    ResearchBudgetExceeded,
    ResearchNodeTimeout,
)
from app.services.research.runner import execute_research_job
from app.services.research.tools import ResearchToolBudget, ResearchToolError
from app.services.retrieval.scope import visible_document_ids

logger = logging.getLogger("research.jobs")
router = APIRouter(prefix="/api/v1", tags=["research"])


def _response(job: ResearchJob) -> ResearchJobResponse:
    return ResearchJobResponse(
        job_id=job.id,
        status=ResearchStatus(job.status),
        query=job.query,
        steps=[ResearchStep.model_validate(step) for step in job.steps],
        tool_calls=[ResearchToolCall.model_validate(call) for call in job.tool_calls],
        iterations=job.iterations,
        tool_calls_count=job.tool_calls_count,
        sufficiency_verdict=job.sufficiency_verdict,
        report=ResearchReport.model_validate(job.report) if job.report else None,
        error_code=job.error_code,
        evidence=[SearchResult.model_validate(item) for item in job.evidence],
    )


async def _persist_step(database: Database, job_id: UUID, step: ResearchStep) -> None:
    async with database.sessions() as session, session.begin():
        job = await session.get(ResearchJob, job_id)
        if job is None:
            raise RuntimeError("Research job disappeared while its graph was running.")
        job.steps = [*job.steps, step.model_dump(mode="json")]
        job.iterations = step.iteration
        job.tool_calls_count = step.tool_calls_count


async def _persist_failure(
    database: Database,
    job_id: UUID,
    error_code: str,
    *,
    node_name: str,
    tool_calls_count: int,
) -> None:
    async with database.sessions() as session, session.begin():
        job = await session.get(ResearchJob, job_id)
        if job is None:
            raise RuntimeError("Research job disappeared while its graph was running.")
        job.status = ResearchStatus.FAILED.value
        job.error_code = error_code
        job.tool_calls_count = min(max(job.tool_calls_count, tool_calls_count), 6)
        job.steps = [
            *job.steps,
            ResearchStep(
                name=node_name,
                status=ResearchStepStatus.FAILED,
                message=f"Execution stopped ({error_code}).",
                iteration=job.iterations,
                tool_calls_count=job.tool_calls_count,
            ).model_dump(mode="json"),
        ]


async def run_research_job(
    database: Database,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    settings: Settings,
    *,
    job_id: UUID,
    session_id: UUID,
) -> None:
    budget = ResearchToolBudget(settings.max_tool_calls)
    try:
        async with database.sessions() as session, session.begin():
            job = await session.get(ResearchJob, job_id)
            if job is None or job.session_id != session_id:
                raise RuntimeError("Research job is unavailable to its worker.")
            if job.status != ResearchStatus.QUEUED.value:
                return
            query, document_ids, top_k = (
                job.query,
                [UUID(identity) for identity in job.document_ids],
                job.top_k,
            )
            job.status = ResearchStatus.RUNNING.value

        async def record_step(step: ResearchStep) -> None:
            await _persist_step(database, job_id, step)

        result = await execute_research_job(
            database,
            embedding_provider,
            llm_provider,
            settings,
            session_id=session_id,
            allowed_doc_ids=document_ids,
            query=query,
            top_k=top_k,
            budget=budget,
            on_step=record_step,
        )
        async with database.sessions() as session, session.begin():
            job = await session.get(ResearchJob, job_id)
            if job is None:
                raise RuntimeError("Research job disappeared after graph completion.")
            job.status = result["status"].value
            job.steps = [step.model_dump(mode="json") for step in result["steps"]]
            job.tool_calls = [call.model_dump(mode="json") for call in result["tool_calls"]]
            job.iterations = result["iterations"]
            job.tool_calls_count = result["tool_calls_count"]
            job.sufficiency_verdict = result["sufficiency_verdict"]
            job.report = (
                result["final_report"].model_dump(mode="json")
                if result["final_report"] is not None
                else None
            )
            job.evidence = [item.model_dump(mode="json") for item in result["retrieved_evidence"]]
            job.error_code = result["error_code"]
    except ResearchNodeTimeout as exc:
        await _persist_failure(
            database,
            job_id,
            exc.error_code,
            node_name=exc.node_name,
            tool_calls_count=budget.tool_calls_count,
        )
        logger.warning(
            "research.node_timed_out",
            extra={"job_id": str(job_id), "node_name": exc.node_name},
        )
    except (
        ResearchToolError,
        ResearchBudgetExceeded,
        LLMProviderError,
        EmbeddingProviderError,
    ) as exc:
        error_code = getattr(exc, "error_code", "RESEARCH_EXECUTION_FAILED")
        await _persist_failure(
            database,
            job_id,
            error_code,
            node_name="execute_tools",
            tool_calls_count=budget.tool_calls_count,
        )
        logger.warning(
            "research.execution_failed", extra={"job_id": str(job_id), "error_code": error_code}
        )
    except SQLAlchemyError:
        logger.exception(
            "research.database_failed",
            extra={"job_id": str(job_id), "error_code": "DATABASE_OPERATION_FAILED"},
        )
        raise


@router.post(
    "/research",
    response_model=ResearchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_research_job(
    request: Request,
    body: ResearchRequest,
    background_tasks: BackgroundTasks,
    response: Response,
) -> ResearchJobResponse:
    session_id = require_session_id(request)
    database: Database = request.app.state.database
    settings: Settings = request.app.state.settings
    allowed_doc_ids = await visible_document_ids(database, session_id, body.document_ids)
    if set(allowed_doc_ids) != set(body.document_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    try:
        async with database.sessions() as session, session.begin():
            await session.execute(
                select(func.pg_advisory_xact_lock(func.hashtextextended(str(session_id), 0)))
            )
            recent_jobs = await session.scalar(
                select(func.count(ResearchJob.id)).where(
                    ResearchJob.session_id == session_id,
                    ResearchJob.created_at >= func.now() - timedelta(minutes=10),
                )
            )
            if (recent_jobs or 0) >= settings.rate_limit_research_per_10min:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Research request limit reached. Try again later.",
                )
            job = ResearchJob(
                session_id=session_id,
                query=body.query,
                document_ids=[str(identity) for identity in allowed_doc_ids],
                top_k=body.top_k,
            )
            session.add(job)
            await session.flush()
    except SQLAlchemyError:
        logger.error(
            "research.job_creation_failed", extra={"error_code": "DATABASE_OPERATION_FAILED"}
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Research service is temporarily unavailable.",
        ) from None

    background_tasks.add_task(
        run_research_job,
        database,
        request.app.state.embedding_provider,
        request.app.state.llm_provider,
        settings,
        job_id=job.id,
        session_id=session_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return _response(job)


@router.get("/research/{job_id}", response_model=ResearchJobResponse)
async def get_research_job(
    job_id: UUID, request: Request, response: Response
) -> ResearchJobResponse:
    session_id = require_session_id(request)
    database: Database = request.app.state.database
    async with database.sessions() as session:
        job = await session.scalar(
            select(ResearchJob).where(
                ResearchJob.id == job_id,
                ResearchJob.session_id == session_id,
            )
        )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research job not found.")
    response.headers["Cache-Control"] = "no-store"
    return _response(job)
