"""Killable native parsing with bounded JSON IPC, not child-controlled pickle."""

import json
import multiprocessing
import os
import queue
import sys
from collections.abc import Callable
from dataclasses import asdict
from multiprocessing.connection import Connection
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from typing import TYPE_CHECKING, Any

from app.services.ingestion.control import check_cancelled
from app.services.ingestion.errors import OCRNotSupportedError, PDFExtractionError
from app.services.ingestion.process_limits import WindowsJob, limit_posix_worker
from app.services.ingestion.validation import PDFValidationError, ValidatedPDF

if TYPE_CHECKING:
    from app.services.ingestion.detection import PDFTextDensityDetector
    from app.services.ingestion.extraction import ExtractedDocument

MAX_MESSAGE_BYTES = 8 * 1024 * 1024
MAX_PAGE_CHARS = 1_000_000
MAX_DOCUMENT_CHARS = 2_000_000
SAFE_VALIDATION_ERRORS = {
    "ENCRYPTED_PDF": ("Encrypted PDFs are not supported.", 422),
    "INVALID_PDF": ("The PDF structure is invalid or damaged.", 400),
    "EMPTY_PDF": ("The PDF must contain at least one page.", 422),
    "PDF_PAGE_LIMIT_EXCEEDED": ("The PDF exceeds the configured page limit.", 422),
}


class PDFParserTimeout(PDFExtractionError):
    error_code = "PDF_PARSER_TIMEOUT"


def run_worker(
    target: Callable[[Connection, dict[str, Any]], None],
    payload: dict[str, Any],
    *,
    timeout_seconds: float = 15,
    max_progress: int = 0,
) -> dict[str, Any]:
    """Only trusted parent configuration is pickled by spawn; replies are JSON bytes.

    Progress must advance exactly once per bounded parsing unit. Repeated or surplus
    heartbeats cannot extend the deadline. Parent owns all files and process cleanup.
    """
    if not 0 < timeout_seconds <= 15 or not 0 <= max_progress <= 104:
        raise ValueError("Invalid parser supervision limits")
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    process = context.Process(target=target, args=(child, payload), daemon=True)
    job = None
    started = False
    reader: Thread | None = None
    stopped = Event()
    inbox: queue.Queue[bytes | Exception] = queue.Queue(maxsize=1)

    def read_messages() -> None:
        while not stopped.is_set():
            try:
                value: bytes | Exception = parent.recv_bytes(MAX_MESSAGE_BYTES)
            except Exception as exc:
                value = exc
            while not stopped.is_set():
                try:
                    inbox.put(value, timeout=0.05)
                    break
                except queue.Full:
                    continue
            if isinstance(value, Exception):
                return

    try:
        check_cancelled()
        process.start()
        started = True
        child.close()
        assert process.pid is not None
        job = WindowsJob(process.pid)
        parent.send_bytes(b"go")  # Parsing cannot begin until OS limits are attached.
        # A partial IPC frame must not block the watchdog in recv_bytes().
        reader = Thread(target=read_messages, name="pdf-ipc-reader", daemon=True)
        reader.start()
        deadline = monotonic() + timeout_seconds
        step = 0
        while True:
            check_cancelled()
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise PDFParserTimeout(message="PDF parsing exceeded its time limit.")
            try:
                encoded = inbox.get(timeout=min(remaining, 0.05))
            except queue.Empty:
                continue
            if isinstance(encoded, Exception):
                raise PDFExtractionError()
            message = json.loads(encoded)
            if not isinstance(message, dict):
                raise PDFExtractionError()
            if message.get("kind") == "progress":
                if type(message.get("step")) is not int or message["step"] != step:
                    raise PDFExtractionError()
                if step >= max_progress:
                    raise PDFExtractionError()
                step += 1
                deadline = monotonic() + timeout_seconds
                continue
            if message.get("kind") not in {"result", "error"}:
                raise PDFExtractionError()
            return message
    except PDFExtractionError:
        raise
    except Exception:
        raise PDFExtractionError() from None
    finally:
        stopped.set()
        child.close()
        if started:
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
        if job is not None:
            job.close()
        parent.close()
        if reader is not None:
            reader.join(timeout=1)


def _worker(connection: Connection, payload: dict[str, Any]) -> None:
    # Child diagnostics from native dependencies must not echo PDF text/paths.
    with open(os.devnull, "w") as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
        sys.stdout = sink
        sys.stderr = sink
        try:
            if connection.recv_bytes(3) != b"go":
                return
            limit_posix_worker()
            if payload["mode"] == "validate":
                from app.services.ingestion.validation import PDFValidator

                count = PDFValidator(max_pdf_pages=payload["max_pages"])._check_structure_native(
                    Path(payload["path"])
                )
                response = {"kind": "result", "page_count": count}
            else:
                from app.services.ingestion.detection import PDFTextDensityDetector
                from app.services.ingestion.extraction import PDFMarkdownExtractor

                pdf = ValidatedPDF(
                    Path(payload["path"]),
                    payload["size_bytes"],
                    payload["page_count"],
                    payload["checksum"],
                )
                step = 0

                def progress() -> None:
                    nonlocal step
                    connection.send_bytes(json.dumps({"kind": "progress", "step": step}).encode())
                    step += 1

                extractor = PDFMarkdownExtractor(
                    text_detector=PDFTextDensityDetector(
                        min_text_chars_per_page=payload["min_chars"],
                        max_low_text_page_percent=payload["max_low_percent"],
                    )
                )
                document = extractor.extract(pdf, progress=progress)
                if sum(len(page.raw_text) for page in document.pages) > MAX_DOCUMENT_CHARS:
                    raise PDFExtractionError()
                response = {"kind": "result", "document": asdict(document)}
        except PDFValidationError as exc:
            response = {"kind": "error", "code": exc.error_code}
        except OCRNotSupportedError as exc:
            response = {
                "kind": "error",
                "code": "OCR_NOT_SUPPORTED",
                "ocr": {
                    "total_pages": exc.total_pages,
                    "checked_pages": exc.checked_pages,
                    "low_text_page_numbers": list(exc.low_text_page_numbers),
                    "min_text_chars_per_page": exc.min_text_chars_per_page,
                    "max_low_text_page_percent": exc.max_low_text_page_percent,
                },
            }
        except Exception:
            response = {"kind": "error", "code": "PDF_EXTRACTION_FAILED"}
        try:
            encoded = json.dumps(response, ensure_ascii=True).encode()
            if len(encoded) > MAX_MESSAGE_BYTES:
                encoded = b'{"kind":"error","code":"PDF_EXTRACTION_FAILED"}'
            connection.send_bytes(encoded)
        finally:
            connection.close()


def validate_structure(path: Path, max_pages: int) -> int:
    message = run_worker(_worker, {"mode": "validate", "path": str(path), "max_pages": max_pages})
    if message["kind"] == "error":
        code = message.get("code")
        if code in SAFE_VALIDATION_ERRORS:
            text, status = SAFE_VALIDATION_ERRORS[code]
            raise PDFValidationError(code, text, status)
        raise PDFExtractionError()
    count = message.get("page_count")
    if type(count) is not int or not 1 <= count <= max_pages:
        raise PDFExtractionError()
    return count


class SandboxedPDFExtractor:
    def __init__(self, *, text_detector: "PDFTextDensityDetector | None" = None) -> None:
        from app.services.ingestion.detection import PDFTextDensityDetector

        self.text_detector = text_detector or PDFTextDensityDetector()

    def extract(self, pdf: ValidatedPDF) -> "ExtractedDocument":
        from app.services.ingestion.detection import TextDensityReport
        from app.services.ingestion.extraction import ExtractedDocument, ExtractedPage

        message = run_worker(
            _worker,
            {
                "mode": "extract",
                "path": str(pdf.path),
                "size_bytes": pdf.size_bytes,
                "page_count": pdf.page_count,
                "checksum": pdf.checksum,
                "min_chars": self.text_detector.min_chars,
                "max_low_percent": self.text_detector.max_low_percent,
            },
            max_progress=pdf.page_count + 4,
        )
        if message["kind"] == "error":
            if message.get("code") == "OCR_NOT_SUPPORTED":
                # Reconstruct only typed, bounded diagnostic fields, never child error text.
                from pydantic import BaseModel, Field

                class OCRDetails(BaseModel):
                    total_pages: int = Field(ge=1, le=100)
                    checked_pages: int = Field(ge=1, le=100)
                    low_text_page_numbers: tuple[int, ...] = Field(max_length=100)
                    min_text_chars_per_page: int = Field(ge=1, le=10000)
                    max_low_text_page_percent: int = Field(ge=0, le=99)

                try:
                    details = OCRDetails.model_validate(message.get("ocr"))
                except ValueError:
                    raise PDFExtractionError() from None
                raise OCRNotSupportedError(**details.model_dump())
            raise PDFExtractionError()
        try:
            body = message["document"]
            pages = body["pages"]
            density = body["text_density"]
            if (
                not isinstance(pages, list)
                or len(pages) != pdf.page_count
                or any(
                    type(page["page_number"]) is not int
                    or page["page_number"] != index
                    or not isinstance(page["raw_text"], str)
                    or len(page["raw_text"]) > MAX_PAGE_CHARS
                    for index, page in enumerate(pages, 1)
                )
                or sum(len(page["raw_text"]) for page in pages) > MAX_DOCUMENT_CHARS
                or body["parser"] != "pymupdf4llm"
                or not isinstance(body["parser_version"], str)
                or len(body["parser_version"]) > 64
                or len(density["text_char_counts"]) != pdf.page_count
                or any(
                    type(n) is not int or not 0 <= n <= MAX_PAGE_CHARS
                    for n in density["text_char_counts"]
                )
                or any(
                    type(n) is not int or not 1 <= n <= pdf.page_count
                    for n in density["low_text_page_numbers"]
                )
            ):
                raise PDFExtractionError()
            return ExtractedDocument(
                checksum=pdf.checksum,
                size_bytes=pdf.size_bytes,
                pages=tuple(ExtractedPage(p["page_number"], p["raw_text"]) for p in pages),
                parser="pymupdf4llm",
                parser_version=body["parser_version"],
                text_density=TextDensityReport(
                    tuple(density["text_char_counts"]),
                    tuple(density["low_text_page_numbers"]),
                    self.text_detector.min_chars,
                    self.text_detector.max_low_percent,
                ),
            )
        except (KeyError, TypeError, ValueError):
            raise PDFExtractionError() from None
