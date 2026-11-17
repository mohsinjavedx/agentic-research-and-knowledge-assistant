"""Periodic deletion of expired, session-owned documents."""

import asyncio
import logging

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.locks import EMBEDDING_INDEX_ADVISORY_LOCK
from app.db.models import Document
from app.db.session import Database

logger = logging.getLogger("research.document_cleanup")
EXPIRED_DOCUMENT_CLEANUP_INTERVAL_SECONDS = 15 * 60


async def cleanup_expired_documents(session: AsyncSession) -> int:
    """Delete expired session documents; the caller owns the transaction."""
    expired = (
        delete(Document)
        .where(Document.session_id.is_not(None))
        .where(Document.is_sample.is_(False))
        .where(Document.expires_at < func.now())
        .returning(Document.id)
        .cte("expired_documents")
    )
    count = await session.scalar(select(func.count()).select_from(expired))
    return int(count or 0)


async def purge_expired_documents(database: Database) -> int:
    async with database.sessions() as session, session.begin():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": EMBEDDING_INDEX_ADVISORY_LOCK},
        )
        return await cleanup_expired_documents(session)


async def run_expired_document_cleanup(database: Database) -> None:
    """Run a cleanup immediately, then periodically; retry database outages."""
    while True:
        try:
            deleted = await purge_expired_documents(database)
        except SQLAlchemyError:
            logger.warning(
                "documents.expiry_cleanup_failed",
                extra={"error_code": "EXPIRY_CLEANUP_FAILED"},
            )
            await asyncio.sleep(min(EXPIRED_DOCUMENT_CLEANUP_INTERVAL_SECONDS, 60))
            continue

        if deleted:
            logger.info("documents.expiry_cleanup_completed", extra={"deleted_documents": deleted})
        await asyncio.sleep(EXPIRED_DOCUMENT_CLEANUP_INTERVAL_SECONDS)
