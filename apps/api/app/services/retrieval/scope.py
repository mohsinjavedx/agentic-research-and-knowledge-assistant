"""Resolve the ready sample and current-session documents visible to a request."""

from uuid import UUID

from sqlalchemy import and_, func, or_, select

from app.db.models import Document
from app.db.session import Database


async def visible_document_ids(
    database: Database, session_id: UUID, requested_ids: list[UUID] | None
) -> list[UUID]:
    owner_scope = and_(
        Document.is_sample.is_(False),
        Document.session_id == session_id,
        or_(Document.expires_at.is_(None), Document.expires_at > func.now()),
    )
    statement = select(Document.id).where(
        Document.status == "ready",
        or_(Document.is_sample.is_(True), owner_scope),
    )
    if requested_ids is not None:
        statement = statement.where(Document.id.in_(requested_ids))
    async with database.sessions() as session:
        return list((await session.scalars(statement)).all())
