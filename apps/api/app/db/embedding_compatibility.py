"""Schema/model checks that never import tokenizers, runtimes or model weights."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.config import Settings
from app.providers.identity import BGE_MODEL, EmbeddingCompatibilityError, EmbeddingIdentity


async def assert_batch_model_compatibility(
    connection: AsyncConnection | AsyncSession, identity: EmbeddingIdentity
) -> None:
    mismatch = await connection.scalar(
        text(
            "SELECT id FROM embedding_batches "
            "WHERE embedding_model <> :model OR model_revision <> :revision "
            "OR embedding_dim <> :dimension LIMIT 1"
        ),
        {"model": identity.model, "revision": identity.revision, "dimension": identity.dimension},
    )
    if mismatch is not None:
        raise EmbeddingCompatibilityError("EMBEDDING_MODEL_MISMATCH")


async def assert_embedding_compatibility(
    connection: AsyncConnection | AsyncSession, settings: Settings
) -> None:
    if settings.embedding_model != BGE_MODEL or settings.embedding_dim != 384:
        raise EmbeddingCompatibilityError("UNSUPPORTED_EMBEDDING_MODEL")
    column_type = await connection.scalar(
        text(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding' AND NOT attisdropped"
        )
    )
    if column_type != f"vector({settings.embedding_dim})":
        raise EmbeddingCompatibilityError("EMBEDDING_DIMENSION_MISMATCH")
    await assert_batch_model_compatibility(connection, EmbeddingIdentity())
