"""Validate a local PDF, or extract its page-by-page Markdown with --extract."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.core.config import load_settings
from app.services.ingestion.errors import OCRNotSupportedError, PDFExtractionError
from app.services.ingestion.validation import PDFValidationError, PDFValidator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "file", type=Path, help="Local PDF to validate; the original is never modified"
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--extract", action="store_true", help="Extract page-by-page Markdown")
    modes.add_argument(
        "--prepare", action="store_true", help="Extract, normalize, and create traceable chunks"
    )
    parser.add_argument(
        "--output", type=Path, help="Write extraction/preparation JSON to a new UTF-8 file"
    )
    arguments = parser.parse_args()
    if arguments.output and not (arguments.extract or arguments.prepare):
        parser.error("--output requires --extract or --prepare")
    if arguments.output and arguments.output.exists():
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_code": "OUTPUT_FILE_EXISTS",
                    "message": "Choose a new output file; the existing file was not changed.",
                }
            )
        )
        return 1
    try:
        settings = load_settings()
        validator = PDFValidator(
            max_upload_mb=settings.max_upload_mb, max_pdf_pages=settings.max_pdf_pages
        )
        with arguments.file.open("rb") as source:
            if arguments.extract or arguments.prepare:
                # Keep parser imports out of the validation-only command.
                from app.services.chunking.splitter import MarkdownChunker
                from app.services.ingestion.detection import PDFTextDensityDetector
                from app.services.ingestion.pipeline import PDFIngestionService
                from app.services.ingestion.sandbox import SandboxedPDFExtractor

                extractor = SandboxedPDFExtractor(
                    text_detector=PDFTextDensityDetector(
                        min_text_chars_per_page=settings.min_text_chars_per_page,
                        max_low_text_page_percent=settings.max_low_text_page_percent,
                    )
                )
                service = PDFIngestionService(
                    validator=validator,
                    extractor=extractor,
                    chunker=MarkdownChunker(
                        min_tokens=settings.chunk_min_tokens,
                        max_tokens=settings.chunk_max_tokens,
                        overlap_tokens=settings.chunk_overlap_tokens,
                    ),
                )
                if arguments.prepare:
                    prepared = service.prepare(source, filename=arguments.file.name)
                    result = {
                        "status": "prepared",
                        "document_id": prepared.document_id,
                        "extraction": asdict(prepared.document.source),
                        "pages": [asdict(page) for page in prepared.document.pages],
                        "chunks": [chunk.model_dump(mode="json") for chunk in prepared.chunks],
                        "page_count": prepared.document.source.page_count,
                    }
                else:
                    document = service.extract(source, filename=arguments.file.name)
                    result = {
                        "status": "extracted",
                        **asdict(document),
                        "page_count": document.page_count,
                    }
            else:
                with validator.validate(source, filename=arguments.file.name) as pdf:
                    result = {
                        "status": "validated",
                        "temporary_filename": pdf.path.name,
                        "size_bytes": pdf.size_bytes,
                        "page_count": pdf.page_count,
                        "checksum": pdf.checksum,
                    }
        # Report only after leaving the context: the temporary PDF is already gone.
        payload = {**result, "temporary_file_deleted": True}
        if arguments.output:
            with arguments.output.open("x", encoding="utf-8") as output:
                json.dump(payload, output, ensure_ascii=False, indent=2)
                output.write("\n")
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "page_count": result["page_count"],
                        "temporary_file_deleted": True,
                        "output_written": True,
                    }
                )
            )
        else:
            # ASCII escapes keep stdout JSON valid on Windows console encodings.
            print(json.dumps(payload))
        return 0
    except PDFValidationError as exc:
        print(json.dumps({"status": "rejected", "error_code": exc.error_code, "message": str(exc)}))
        return 2
    except PDFExtractionError as exc:
        failure: dict[str, object] = {
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
        print(json.dumps(failure))
        return 2
    except OSError:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_code": "FILE_IO_ERROR",
                    "message": "Could not read the input file or use temporary storage.",
                }
            )
        )
        return 1
    except RuntimeError as exc:
        print(
            json.dumps(
                {"status": "error", "error_code": "CONFIGURATION_ERROR", "message": str(exc)}
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
