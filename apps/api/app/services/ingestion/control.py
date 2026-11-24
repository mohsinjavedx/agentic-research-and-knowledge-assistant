"""Cooperative parent-side cancellation; native work is killed by its supervisor."""

from contextvars import ContextVar
from threading import Event

from app.services.ingestion.errors import PDFExtractionError

cancellation_context: ContextVar[Event | None] = ContextVar("pdf_cancellation", default=None)


class PDFPreparationCancelled(PDFExtractionError):
    error_code = "PDF_PREPARATION_CANCELLED"


def check_cancelled() -> None:
    cancellation = cancellation_context.get()
    if cancellation is not None and cancellation.is_set():
        raise PDFPreparationCancelled(message="PDF preparation was cancelled.")
