"""Serialize native PDF parsing on one app-owned worker and own stream cleanup."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import BinaryIO
from uuid import uuid4

from app.core.config import Settings
from app.providers.embeddings import EmbeddingProvider, EmbeddingProviderError
from app.services.indexing.processor import embed_stream
from app.services.indexing.service import EmbeddedDocument


def _prepare(
    settings: Settings,
    provider: EmbeddingProvider,
    source: BinaryIO,
    filename: str,
    content_type: str,
) -> EmbeddedDocument:
    with source:
        return embed_stream(
            settings,
            provider,
            source,
            filename=filename,
            content_type=content_type,
            document_id=uuid4(),
        )


class PDFUploadProcessor:
    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pdf-upload")

    async def prepare(
        self,
        settings: Settings,
        provider: EmbeddingProvider,
        source: BinaryIO,
        filename: str,
        content_type: str,
    ) -> EmbeddedDocument:
        try:
            future = self._pool.submit(_prepare, settings, provider, source, filename, content_type)
        except RuntimeError:
            source.close()
            raise EmbeddingProviderError("UPLOAD_PROCESSOR_UNAVAILABLE") from None
        try:
            # A cancelled HTTP caller must not abandon an open queued stream.
            return await asyncio.shield(asyncio.wrap_future(future))
        except asyncio.CancelledError:
            if future.cancel():
                source.close()
            # Running work closes its source in _prepare; no document is persisted.
            raise

    def close(self) -> None:
        self._pool.shutdown(wait=True, cancel_futures=False)
