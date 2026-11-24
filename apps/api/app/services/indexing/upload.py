"""Serialize native PDF parsing on one app-owned worker and own stream cleanup."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from threading import Event
from typing import BinaryIO
from uuid import uuid4

from app.core.config import Settings
from app.providers.embeddings import EmbeddingProvider, EmbeddingProviderError
from app.services.indexing.processor import embed_stream
from app.services.indexing.service import EmbeddedDocument
from app.services.ingestion.control import cancellation_context, check_cancelled


def _prepare(
    settings: Settings,
    provider: EmbeddingProvider,
    source: BinaryIO,
    filename: str,
    content_type: str,
) -> EmbeddedDocument:
    with source:
        check_cancelled()
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
        cancellation = Event()
        cancellation_token = cancellation_context.set(cancellation)
        try:
            future = self._pool.submit(
                copy_context().run, _prepare, settings, provider, source, filename, content_type
            )
        except RuntimeError:
            source.close()
            raise EmbeddingProviderError("UPLOAD_PROCESSOR_UNAVAILABLE") from None
        finally:
            cancellation_context.reset(cancellation_token)
        wrapped = asyncio.wrap_future(future)
        try:
            # A cancelled HTTP caller must not abandon an open queued stream.
            return await asyncio.shield(wrapped)
        except asyncio.CancelledError:
            cancellation.set()
            if future.cancel():
                source.close()
            else:
                # Do not return cancellation while a parser/staged source survives.
                # Repeated caller cancellation cannot abandon this cleanup wait.
                while not wrapped.done():
                    try:
                        await asyncio.shield(wrapped)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                if not wrapped.cancelled():
                    wrapped.exception()  # Consume the discarded worker result/error.
            raise

    def close(self) -> None:
        self._pool.shutdown(wait=True, cancel_futures=False)
