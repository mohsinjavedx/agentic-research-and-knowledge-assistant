"""Prepare and embed a PDF with the configured indexing pipeline."""

from pathlib import Path
from uuid import UUID

from app.core.config import Settings
from app.providers.embeddings import EmbeddingProvider
from app.services.indexing.preparation import embedding_chunker
from app.services.indexing.service import EmbeddedDocument
from app.services.ingestion.detection import PDFTextDensityDetector
from app.services.ingestion.extraction import PDFMarkdownExtractor
from app.services.ingestion.pipeline import PDFIngestionService
from app.services.ingestion.validation import PDFValidator


def embed_pdf(
    settings: Settings,
    provider: EmbeddingProvider,
    file: Path,
    *,
    document_id: UUID | None = None,
) -> EmbeddedDocument:
    validator = PDFValidator(
        max_upload_mb=settings.max_upload_mb, max_pdf_pages=settings.max_pdf_pages
    )
    extractor = PDFMarkdownExtractor(
        text_detector=PDFTextDensityDetector(
            min_text_chars_per_page=settings.min_text_chars_per_page,
            max_low_text_page_percent=settings.max_low_text_page_percent,
        )
    )
    ingestion = PDFIngestionService(
        validator=validator,
        extractor=extractor,
        chunker=embedding_chunker(settings, provider),
    )
    with file.open("rb") as source:
        prepared = ingestion.prepare(source, filename=file.name, document_id=document_id)
    vectors = provider.embed_documents([chunk.normalized_text for chunk in prepared.chunks])
    return EmbeddedDocument(
        document_id=UUID(prepared.document_id),
        checksum=prepared.document.source.checksum,
        page_count=prepared.document.source.page_count,
        chunks=prepared.chunks,
        vectors=tuple(tuple(vector) for vector in vectors),
        identity=provider.identity,
        provider=provider.kind,
    )
