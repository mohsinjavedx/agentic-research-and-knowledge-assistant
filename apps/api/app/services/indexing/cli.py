"""Prepare and embed a PDF, optionally persisting it in PostgreSQL."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, load_settings
from app.db.session import Database
from app.providers.embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
    create_embedding_provider,
)
from app.providers.identity import EmbeddingCompatibilityError
from app.services.indexing.preparation import embedding_chunker
from app.services.indexing.service import EmbeddedDocument, persist_document
from app.services.ingestion.detection import PDFTextDensityDetector
from app.services.ingestion.errors import OCRNotSupportedError, PDFExtractionError
from app.services.ingestion.extraction import PDFMarkdownExtractor
from app.services.ingestion.pipeline import PDFIngestionService
from app.services.ingestion.validation import PDFValidationError, PDFValidator


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Local PDF to prepare and embed")
    parser.add_argument(
        "--persist", action="store_true", help="Persist the document and embeddings in PostgreSQL"
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--sample", action="store_true", help="Persist as a global read-only sample document"
    )
    scope.add_argument(
        "--session-id", type=UUID, help="Persist under this anonymous browser session"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Export chunk text, provenance, and embeddings to a new JSON file",
    )
    arguments = parser.parse_args()
    if arguments.persist and not (arguments.sample or arguments.session_id):
        parser.error("--persist requires --sample or --session-id")
    if not arguments.persist and (arguments.sample or arguments.session_id):
        parser.error("--sample and --session-id require --persist")
    return arguments


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True))


def _write_export(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write("\n")


def _prepare(
    settings: Settings, provider: EmbeddingProvider, file: Path, *, document_id: UUID | None
) -> tuple[EmbeddedDocument, dict[str, Any]]:
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
    document = EmbeddedDocument(
        document_id=UUID(prepared.document_id),
        checksum=prepared.document.source.checksum,
        page_count=prepared.document.source.page_count,
        chunks=prepared.chunks,
        vectors=tuple(tuple(vector) for vector in vectors),
        identity=provider.identity,
        provider=provider.kind,
    )
    export = {
        "status": "embedded",
        "document_id": prepared.document_id,
        "checksum": document.checksum,
        "page_count": document.page_count,
        "embedding_model": document.identity.model,
        "model_revision": document.identity.revision,
        "embedding_dim": document.identity.dimension,
        "provider": document.provider,
        "chunks": [
            {
                **chunk.model_dump(mode="json"),
                "embedding": vector,
            }
            for chunk, vector in zip(document.chunks, document.vectors, strict=True)
        ],
    }
    return document, export


async def _persist(
    settings: Settings,
    embedded: EmbeddedDocument,
    filename: str,
    *,
    is_sample: bool,
    session_id: UUID | None,
) -> UUID:
    database = Database(settings)
    try:
        await database.check()
        return await persist_document(
            database,
            embedded,
            filename=filename,
            is_sample=is_sample,
            session_id=session_id,
        )
    finally:
        await database.close()


def main() -> int:
    arguments = _arguments()
    if arguments.output is not None and arguments.output.exists():
        _emit(
            {
                "status": "error",
                "error_code": "OUTPUT_FILE_EXISTS",
                "message": "Choose a new output file; the existing file was not changed.",
            }
        )
        return 1

    provider: EmbeddingProvider | None = None
    try:
        settings = load_settings()
        provider = create_embedding_provider(settings)
        embedded, export = _prepare(
            settings,
            provider,
            arguments.file,
            document_id=uuid4() if arguments.persist else None,
        )

        if arguments.persist:
            document_id = asyncio.run(
                _persist(
                    settings,
                    embedded,
                    arguments.file.name,
                    is_sample=arguments.sample,
                    session_id=arguments.session_id,
                )
            )
            export["status"] = "indexed"
            export["document_id"] = str(document_id)

        if arguments.output is not None:
            _write_export(arguments.output, export)
            _emit(
                {
                    "status": export["status"],
                    "document_id": export["document_id"],
                    "page_count": export["page_count"],
                    "chunk_count": len(export["chunks"]),
                    "output_written": True,
                }
            )
        else:
            _emit(
                {
                    "status": export["status"],
                    "document_id": export["document_id"],
                    "checksum": export["checksum"],
                    "page_count": export["page_count"],
                    "chunk_count": len(export["chunks"]),
                    "embedding_model": export["embedding_model"],
                    "embedding_dim": export["embedding_dim"],
                    "provider": export["provider"],
                }
            )
        return 0
    except FileNotFoundError:
        _emit({"status": "error", "error_code": "FILE_IO_ERROR", "message": "PDF file not found."})
        return 1
    except FileExistsError:
        _emit(
            {
                "status": "error",
                "error_code": "OUTPUT_FILE_EXISTS",
                "message": "Choose a new output file; the existing file was not changed.",
            }
        )
        return 1
    except OSError:
        _emit(
            {
                "status": "error",
                "error_code": "FILE_IO_ERROR",
                "message": "Could not read the PDF or write the requested export.",
            }
        )
        return 1
    except PDFValidationError as exc:
        _emit({"status": "failed", "error_code": exc.error_code, "message": str(exc)})
        return 2
    except PDFExtractionError as exc:
        failure: dict[str, Any] = {
            "status": exc.status,
            "error_code": exc.error_code,
            "message": str(exc),
            "page_number": exc.page_number,
        }
        if isinstance(exc, OCRNotSupportedError):
            failure["text_density"] = {
                "total_pages": exc.total_pages,
                "checked_pages": exc.checked_pages,
                "low_text_page_numbers": exc.low_text_page_numbers,
                "min_text_chars_per_page": exc.min_text_chars_per_page,
                "max_low_text_page_percent": exc.max_low_text_page_percent,
            }
        _emit(failure)
        return 2
    except EmbeddingProviderError as exc:
        _emit({"status": "failed", "error_code": exc.error_code, "message": str(exc)})
        return 2
    except EmbeddingCompatibilityError:
        _emit(
            {
                "status": "error",
                "error_code": "EMBEDDING_CONFIGURATION_MISMATCH",
                "message": "Database embedding configuration is incompatible.",
            }
        )
        return 1
    except SQLAlchemyError:
        _emit(
            {
                "status": "error",
                "error_code": "DATABASE_OPERATION_FAILED",
                "message": "Could not verify or persist the embedding index.",
            }
        )
        return 1
    except RuntimeError as exc:
        _emit({"status": "error", "error_code": "CONFIGURATION_ERROR", "message": str(exc)})
        return 1
    finally:
        if provider is not None:
            provider.close()


if __name__ == "__main__":
    raise SystemExit(main())
