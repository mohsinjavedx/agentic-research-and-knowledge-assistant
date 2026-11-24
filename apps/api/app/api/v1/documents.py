"""Session-scoped document operations."""

import logging
from tempfile import SpooledTemporaryFile
from typing import BinaryIO, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.sessions import require_session_id
from app.core.config import Settings
from app.core.telemetry import set_error_code
from app.db.models import Document
from app.db.session import Database
from app.providers.embeddings import EmbeddingProvider, EmbeddingProviderError
from app.services.indexing.service import persist_document
from app.services.indexing.upload import PDFUploadProcessor
from app.services.ingestion.errors import PDFExtractionError
from app.services.ingestion.validation import PDFValidationError
from app.services.retrieval.scope import visible_document_ids

router = APIRouter(prefix="/api/v1", tags=["documents"])
logger = logging.getLogger("research.documents")


class DocumentSummary(BaseModel):
    document_id: UUID
    filename: str
    page_count: int | None
    is_sample: bool
    status: str


def _summary(document: Document) -> DocumentSummary:
    return DocumentSummary(
        document_id=document.id,
        filename=document.filename,
        page_count=document.page_count,
        is_sample=document.is_sample,
        status=document.status,
    )


@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents(request: Request) -> list[DocumentSummary]:
    session_id = require_session_id(request)
    database: Database = request.app.state.database
    try:
        visible = await visible_document_ids(database, session_id, None)
        async with database.sessions() as session:
            documents = (
                await session.scalars(
                    select(Document)
                    .where(Document.id.in_(visible))
                    .order_by(Document.is_sample.desc(), Document.created_at.desc())
                    .limit(100)
                )
            ).all()
            return [_summary(document) for document in documents]
    except SQLAlchemyError:
        raise HTTPException(503, "The document library is temporarily unavailable.") from None


@router.post("/documents", response_model=DocumentSummary, status_code=201)
async def upload_document(
    request: Request, filename: str = Query(max_length=255)
) -> DocumentSummary:
    """Accept a raw PDF body; read at most the configured byte limit plus one chunk."""
    session_id = require_session_id(request)
    settings: Settings = request.app.state.settings
    database: Database = request.app.state.database
    provider: EmbeddingProvider = request.app.state.embedding_provider
    processor: PDFUploadProcessor = request.app.state.upload_processor
    source = SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
    handed_off = False
    try:
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > settings.max_upload_mb * 1024 * 1024:
                raise PDFValidationError(
                    "FILE_TOO_LARGE", "Choose a smaller PDF within the upload limit.", 413
                )
            source.write(chunk)
        source.seek(0)
        handed_off = True
        embedded = await processor.prepare(
            settings,
            provider,
            cast(BinaryIO, source),
            filename,
            request.headers.get("content-type", ""),
        )
        identity = await persist_document(
            database, embedded, filename=filename, session_id=session_id
        )
        async with database.sessions() as session:
            document = await session.get(Document, identity)
            if document is None:
                raise HTTPException(503, "The uploaded document could not be loaded.")
            return _summary(document)
    except (PDFValidationError, PDFExtractionError) as exc:
        set_error_code(exc.error_code)
        raise HTTPException(
            exc.status_code,
            detail={
                "code": exc.error_code,
                "message": str(exc),
            },
        ) from None
    except (EmbeddingProviderError, SQLAlchemyError):
        logger.error("document.upload_failed", extra={"error_code": "DOCUMENT_INDEX_FAILED"})
        raise HTTPException(
            503, "Document indexing is temporarily unavailable. Try again."
        ) from None
    finally:
        if not handed_off:
            source.close()


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID, request: Request, response: Response) -> Response:
    session_id = require_session_id(request)
    database: Database = request.app.state.database
    async with database.sessions() as session, session.begin():
        deleted_id = await session.scalar(
            delete(Document)
            .where(Document.id == document_id)
            .where(Document.session_id == session_id)
            .where(Document.is_sample.is_(False))
            .returning(Document.id)
        )
    if deleted_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    response.status_code = status.HTTP_204_NO_CONTENT
    response.headers["Cache-Control"] = "no-store"
    return response
