"""Crash recovery runs once after a successful startup database check."""

from datetime import timedelta

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document


async def recover_interrupted_documents(session: AsyncSession) -> int:
    """Caller owns the transaction; fresh work and terminal states are untouched."""
    statement = (
        update(Document)
        .where(Document.status.in_(("queued", "processing")))
        .where(Document.updated_at < func.now() - timedelta(minutes=5))
        .values(status="failed", error_code="INTERRUPTED_BY_RESTART", updated_at=func.now())
        .returning(Document.id)
    )
    result = await session.execute(statement)
    return len(result.scalars().all())
