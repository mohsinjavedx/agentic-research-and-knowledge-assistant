from hashlib import sha256

from app.services.ingestion.detection import TextDensityReport
from app.services.ingestion.extraction import ExtractedDocument, ExtractedPage


def extracted_document(*texts: str) -> ExtractedDocument:
    data = "\f".join(texts).encode("utf-8")
    return ExtractedDocument(
        checksum=sha256(data).hexdigest(),
        size_bytes=len(data),
        pages=tuple(ExtractedPage(index, text) for index, text in enumerate(texts, start=1)),
        parser="fixture",
        parser_version="1",
        text_density=TextDensityReport(
            tuple(sum(not char.isspace() for char in text) for text in texts), (), 50, 80
        ),
    )
