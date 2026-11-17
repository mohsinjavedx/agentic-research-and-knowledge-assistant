"""Session-scoped document operations."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import delete

from app.api.v1.sessions import require_session_id
from app.db.models import Document
from app.db.session import Database

router = APIRouter(prefix="/api/v1", tags=["documents"])


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
