"""Compose validation and extraction while keeping staged PDFs temporary."""

from dataclasses import dataclass
from typing import BinaryIO
from uuid import NAMESPACE_URL, UUID, uuid5

from app.schemas.chunks import ChunkSchema
from app.services.chunking.splitter import MarkdownChunker
from app.services.ingestion.errors import PDFExtractionError
from app.services.ingestion.extraction import ExtractedDocument, PDFMarkdownExtractor
from app.services.ingestion.normalization import MarkdownNormalizer, NormalizedDocument
from app.services.ingestion.validation import PDFValidator


@dataclass(frozen=True)
class PreparedDocument:
    document_id: str
    document: NormalizedDocument
    chunks: tuple[ChunkSchema, ...]


class PDFIngestionService:
    def __init__(
        self,
        *,
        validator: PDFValidator | None = None,
        extractor: PDFMarkdownExtractor | None = None,
        normalizer: MarkdownNormalizer | None = None,
        chunker: MarkdownChunker | None = None,
    ) -> None:
        self.validator = validator or PDFValidator()
        self.extractor = extractor or PDFMarkdownExtractor()
        self.normalizer = normalizer or MarkdownNormalizer()
        self.chunker = chunker or MarkdownChunker()

    def extract(
        self, source: BinaryIO, *, filename: str, content_type: str = "application/pdf"
    ) -> ExtractedDocument:
        with self.validator.validate(source, filename=filename, content_type=content_type) as pdf:
            # All parser handles close before the validator removes the temporary PDF.
            return self.extractor.extract(pdf)

    def prepare(
        self,
        source: BinaryIO,
        *,
        filename: str,
        content_type: str = "application/pdf",
        document_id: UUID | None = None,
    ) -> PreparedDocument:
        extracted = self.extract(source, filename=filename, content_type=content_type)
        identity = document_id or uuid5(NAMESPACE_URL, "research-pdf:" + extracted.checksum)
        normalized = self.normalizer.normalize(extracted)
        chunks = self.chunker.split(normalized, document_id=identity)
        if not chunks:
            raise PDFExtractionError(message="No indexable text remains after boundary cleanup.")
        return PreparedDocument(str(identity), normalized, chunks)
