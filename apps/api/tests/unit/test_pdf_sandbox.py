import json
import multiprocessing
import os
import time
from io import BytesIO

import pytest

from app.services.ingestion.errors import PDFExtractionError
from app.services.ingestion.pipeline import PDFIngestionService
from app.services.ingestion.sandbox import run_worker
from app.services.ingestion.validation import PDFValidationError, PDFValidator


def stalled_worker(connection, payload):
    connection.recv_bytes()
    time.sleep(60)


def crashed_worker(connection, payload):
    connection.recv_bytes()
    os._exit(9)


def oversized_worker(connection, payload):
    connection.recv_bytes()
    connection.send_bytes(b"x" * (9 * 1024 * 1024))


def invalid_worker(connection, payload):
    connection.recv_bytes()
    connection.send_bytes(b"not-json PRIVATE_DOCUMENT_SENTINEL")


def repeating_progress_worker(connection, payload):
    connection.recv_bytes()
    for _ in range(100):
        connection.send_bytes(json.dumps({"kind": "progress", "step": 0}).encode())


@pytest.mark.parametrize(
    "worker",
    [stalled_worker, crashed_worker, oversized_worker, invalid_worker, repeating_progress_worker],
)
def test_bad_worker_is_bounded_sanitized_and_joined(worker):
    before = {child.pid for child in multiprocessing.active_children()}
    started = time.monotonic()
    with pytest.raises(PDFExtractionError) as caught:
        run_worker(worker, {}, timeout_seconds=2, max_progress=2)
    assert time.monotonic() - started < 8
    assert "PRIVATE_DOCUMENT" not in str(caught.value)
    assert {child.pid for child in multiprocessing.active_children()} == before


def test_safe_default_pipeline_extracts_real_pdf_and_removes_staging(tmp_path, layout_pdf):
    validator = PDFValidator(temp_root=tmp_path)
    result = PDFIngestionService(validator=validator).extract(
        BytesIO(layout_pdf("text")), filename="paper.pdf"
    )
    assert "Evidence stays attached" in result.pages[0].raw_text
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "data,filename,code",
    [
        (b"%PDF-1.7\nPRIVATE_DOCUMENT_SENTINEL\n%%EOF", "paper.pdf", "INVALID_PDF"),
        (b"%PDF-1.7\n", "../../etc/passwd", "INVALID_FILENAME"),
        (b"%PDF-" + b" " * (20 * 1024 * 1024), "paper.pdf", "FILE_TOO_LARGE"),
    ],
)
def test_invalid_input_is_safe_and_leaves_no_staged_pdf(tmp_path, data, filename, code):
    with pytest.raises(PDFValidationError) as caught:
        PDFIngestionService(validator=PDFValidator(temp_root=tmp_path)).extract(
            BytesIO(data), filename=filename
        )
    assert caught.value.error_code == code
    assert "PRIVATE_DOCUMENT" not in str(caught.value)
    assert list(tmp_path.iterdir()) == []
