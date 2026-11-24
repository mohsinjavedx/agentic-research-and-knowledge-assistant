import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.services.ingestion.cli import main


def test_cli_accepts_pdf_and_confirms_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "paper.pdf"
    with PdfWriter() as writer:
        writer.add_blank_page(width=100, height=100)
        writer.write(source)
    monkeypatch.setattr("sys.argv", ["validate", str(source)])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "validated"
    assert result["page_count"] == 1
    assert result["temporary_file_deleted"] is True
    assert source.exists()


def test_cli_rejects_malformed_pdf_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\nPRIVATE_DOCUMENT_SENTINEL\n%%EOF")
    monkeypatch.setattr("sys.argv", ["validate", str(source)])
    assert main() == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["error_code"] == "INVALID_PDF"
    assert "PRIVATE_DOCUMENT_SENTINEL" not in output.out + output.err
    assert "Traceback" not in output.out + output.err


def test_cli_missing_file_returns_safe_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.argv", ["validate", str(tmp_path / "missing.pdf")])
    assert main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["error_code"] == "FILE_IO_ERROR"
    assert str(tmp_path) not in result["message"]


def test_cli_extracts_pages_and_writes_utf8_json(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(layout_pdf("multipage"))
    output = tmp_path / "pages.json"
    monkeypatch.setattr("sys.argv", ["extract", str(source), "--extract", "--output", str(output)])
    assert main() == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["output_written"] is True
    assert summary["temporary_file_deleted"] is True
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "extracted"
    assert result["page_count"] == 3
    assert [page["page_number"] for page in result["pages"]] == [1, 2, 3]
    assert "First page evidence" in result["pages"][0]["raw_text"]
    assert b"Caf\xc3\xa9" in output.read_bytes()
    assert not result["pages"][1]["raw_text"].strip()


def test_cli_can_print_extracted_json_without_an_output_file(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(layout_pdf("text"))
    monkeypatch.setattr("sys.argv", ["extract", str(source), "--extract"])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert "Evidence stays attached" in result["pages"][0]["raw_text"]
    assert "Caf\u00e9" in result["pages"][0]["raw_text"]


def test_cli_never_overwrites_existing_output_or_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"original content")
    monkeypatch.setattr("sys.argv", ["extract", str(source), "--extract", "--output", str(source)])
    assert main() == 1
    assert json.loads(capsys.readouterr().out)["error_code"] == "OUTPUT_FILE_EXISTS"
    assert source.read_bytes() == b"original content"


def test_cli_extraction_failure_does_not_create_an_output_file(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.services.ingestion.errors import PDFExtractionError
    from app.services.ingestion.sandbox import SandboxedPDFExtractor

    def fail(*args: object, **kwargs: object) -> None:
        raise PDFExtractionError(page_number=1)

    monkeypatch.setattr(SandboxedPDFExtractor, "extract", fail)
    source = tmp_path / "source.pdf"
    source.write_bytes(layout_pdf("text"))
    output = tmp_path / "pages.json"
    monkeypatch.setattr("sys.argv", ["extract", str(source), "--extract", "--output", str(output)])
    assert main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error_code"] == "PDF_EXTRACTION_FAILED"
    assert result["page_number"] == 1
    assert not output.exists()


def test_cli_scanned_pdf_has_failed_status_safe_details_and_no_export(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(layout_pdf("image"))
    output = tmp_path / "pages.json"
    monkeypatch.setattr("sys.argv", ["extract", str(source), "--extract", "--output", str(output)])
    assert main() == 2
    captured = capsys.readouterr()
    failure = json.loads(captured.out)
    assert failure["status"] == "failed"
    assert failure["error_code"] == "OCR_NOT_SUPPORTED"
    assert failure["text_density"]["total_pages"] == 1
    assert failure["text_density"]["low_text_page_numbers"] == [1]
    assert "text-based PDF" in failure["message"]
    assert str(tmp_path) not in captured.out
    assert "Traceback" not in captured.out + captured.err
    assert not output.exists()


def test_cli_uses_configured_density_settings(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(layout_pdf("text"))
    monkeypatch.setenv("MIN_TEXT_CHARS_PER_PAGE", "10000")
    monkeypatch.setenv("MAX_LOW_TEXT_PAGE_PERCENT", "0")
    monkeypatch.setattr("sys.argv", ["extract", str(source), "--extract"])
    assert main() == 2
    failure = json.loads(capsys.readouterr().out)
    assert failure["error_code"] == "OCR_NOT_SUPPORTED"
    assert failure["text_density"]["min_text_chars_per_page"] == 10000
    assert failure["text_density"]["max_low_text_page_percent"] == 0


def test_cli_prepares_normalized_pages_and_traceable_chunks(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(layout_pdf("headers"))
    output = tmp_path / "prepared.json"
    monkeypatch.setattr("sys.argv", ["prepare", str(source), "--prepare", "--output", str(output)])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "prepared"
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["temporary_file_deleted"] is True
    assert result["document_id"]
    assert result["chunks"]
    for page in result["pages"]:
        assert "Research journal running header" in page["raw_text"]
        assert "Research journal running header" not in page["normalized_text"]
        assert "Journal footer retained for cleanup" not in page["normalized_text"]
    for chunk in result["chunks"]:
        page = result["pages"][chunk["page_start"] - 1]
        assert page["raw_text"][chunk["char_start"] : chunk["char_end"]] == chunk["raw_text"]
        assert chunk["document_id"] == result["document_id"]
        assert chunk["page_start"] == chunk["page_end"]
        assert chunk["char_end"] > chunk["char_start"]
