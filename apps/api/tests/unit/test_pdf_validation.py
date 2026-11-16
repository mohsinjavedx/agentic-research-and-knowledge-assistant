from hashlib import sha256
from io import BytesIO, UnsupportedOperation
from pathlib import Path
from uuid import UUID

import pytest
from pypdf import PdfWriter

from app.services.ingestion.validation import MEBIBYTE, PDFValidationError, PDFValidator


def make_pdf(page_count: int = 1, *, password: str | None = None) -> bytes:
    with PdfWriter() as writer:
        for _ in range(page_count):
            writer.add_blank_page(width=100, height=100)
        if password is not None:
            writer.encrypt(password, algorithm="RC4-128")
        output = BytesIO()
        writer.write(output)
        return output.getvalue()


def padded_pdf(size: int) -> bytes:
    data = make_pdf()
    position = data.rindex(b"startxref")
    padding = b"%" + b" " * (size - len(data) - 2) + b"\n"
    return data[:position] + padding + data[position:]


def test_valid_pdf_uses_uuid_path_and_is_deleted_after_use(tmp_path: Path) -> None:
    data = make_pdf(2)
    source = BytesIO(data)
    with PDFValidator(temp_root=tmp_path).validate(source, filename="paper.pdf") as pdf:
        staged_path = pdf.path
        assert pdf.path.parent.parent == tmp_path
        assert UUID(pdf.path.stem).version == 4
        assert pdf.path.suffix == ".pdf"
        assert pdf.path.name != "paper.pdf"
        assert pdf.path.read_bytes() == data
        assert pdf.size_bytes == len(data)
        assert pdf.page_count == 2
        assert pdf.checksum == sha256(data).hexdigest()
    assert not staged_path.exists()
    assert list(tmp_path.iterdir()) == []
    assert not source.closed


@pytest.mark.parametrize("filename", ["paper.pdf", "paper.PDF", "research notes.PdF"])
def test_pdf_extension_is_case_insensitive(tmp_path: Path, filename: str) -> None:
    with PDFValidator(temp_root=tmp_path).validate(BytesIO(make_pdf()), filename=filename):
        pass


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "../paper.pdf",
        "..\\paper.pdf",
        "/tmp/paper.pdf",
        "C:\\paper.pdf",
        "paper.pdf\x00.exe",
        "paper\npdf.pdf",
        " paper.pdf",
        "paper.pdf ",
        "x" * 256 + ".pdf",
    ],
)
def test_unsafe_filenames_are_rejected_without_staging(tmp_path: Path, filename: str) -> None:
    with pytest.raises(PDFValidationError) as caught:
        with PDFValidator(temp_root=tmp_path).validate(BytesIO(make_pdf()), filename=filename):
            pytest.fail("Unsafe filename was accepted")
    assert caught.value.error_code == "INVALID_FILENAME"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("filename", ["paper.txt", "paper.pdf.exe", "paper", ".pdf"])
def test_non_pdf_extensions_are_rejected(tmp_path: Path, filename: str) -> None:
    with pytest.raises(PDFValidationError) as caught:
        with PDFValidator(temp_root=tmp_path).validate(BytesIO(make_pdf()), filename=filename):
            pytest.fail("Wrong file extension was accepted")
    assert caught.value.error_code == "UNSUPPORTED_FILE_TYPE"
    assert caught.value.status_code == 415


@pytest.mark.parametrize(
    "content_type", ["text/plain", "image/png", "application/octet-stream", ""]
)
def test_misleading_mime_type_is_rejected(tmp_path: Path, content_type: str) -> None:
    with pytest.raises(PDFValidationError) as caught:
        with PDFValidator(temp_root=tmp_path).validate(
            BytesIO(make_pdf()), filename="paper.pdf", content_type=content_type
        ):
            pytest.fail("Wrong MIME type was accepted")
    assert caught.value.error_code == "UNSUPPORTED_MEDIA_TYPE"
    assert list(tmp_path.iterdir()) == []


def test_mime_parameters_and_case_are_supported(tmp_path: Path) -> None:
    with PDFValidator(temp_root=tmp_path).validate(
        BytesIO(make_pdf()), filename="paper.pdf", content_type="Application/PDF; version=1.7"
    ):
        pass


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"", "EMPTY_FILE"),
        (b"%PD", "INVALID_PDF_SIGNATURE"),
        (b"<html>not a PDF</html>", "INVALID_PDF_SIGNATURE"),
        (b"\n%PDF-1.7", "INVALID_PDF_SIGNATURE"),
        (b"%PDF-1.7\nnot a valid PDF\n%%EOF", "INVALID_PDF"),
    ],
)
def test_empty_disguised_and_malformed_files_fail_safely(
    tmp_path: Path,
    data: bytes,
    code: str,
) -> None:
    with pytest.raises(PDFValidationError) as caught:
        with PDFValidator(temp_root=tmp_path).validate(BytesIO(data), filename="paper.pdf"):
            pytest.fail("Invalid PDF was accepted")
    assert caught.value.error_code == code
    assert list(tmp_path.iterdir()) == []


def test_pdf_exactly_at_twenty_mebibytes_is_accepted(tmp_path: Path) -> None:
    data = padded_pdf(20 * MEBIBYTE)
    with PDFValidator(temp_root=tmp_path).validate(BytesIO(data), filename="paper.pdf") as pdf:
        assert pdf.size_bytes == 20 * MEBIBYTE
        assert pdf.page_count == 1


def test_one_byte_over_twenty_mebibytes_stops_before_parsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_parse(*args: object, **kwargs: object) -> None:
        pytest.fail("Oversized PDF must not reach the parser")

    monkeypatch.setattr("app.services.ingestion.validation.PdfReader", unexpected_parse)
    source = BytesIO(b"%PDF-" + b"x" * (20 * MEBIBYTE + 100))
    with pytest.raises(PDFValidationError) as caught:
        with PDFValidator(temp_root=tmp_path).validate(source, filename="paper.pdf"):
            pytest.fail("Oversized file was accepted")
    assert caught.value.error_code == "FILE_TOO_LARGE"
    assert caught.value.status_code == 413
    assert source.tell() == 20 * MEBIBYTE + 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("pages", "error_code"),
    [
        (0, "EMPTY_PDF"),
        (1, None),
        (100, None),
        (101, "PDF_PAGE_LIMIT_EXCEEDED"),
    ],
)
def test_page_count_boundaries(tmp_path: Path, pages: int, error_code: str | None) -> None:
    source = BytesIO(make_pdf(pages))
    if error_code:
        with pytest.raises(PDFValidationError) as caught:
            with PDFValidator(temp_root=tmp_path).validate(source, filename="paper.pdf"):
                pytest.fail("Out-of-range page count was accepted")
        assert caught.value.error_code == error_code
        assert list(tmp_path.iterdir()) == []
    else:
        with PDFValidator(temp_root=tmp_path).validate(source, filename="paper.pdf") as pdf:
            assert pdf.page_count == pages


@pytest.mark.parametrize("password", ["secret", ""])
def test_encrypted_pdf_is_rejected_even_with_empty_password(tmp_path: Path, password: str) -> None:
    with pytest.raises(PDFValidationError) as caught:
        with PDFValidator(temp_root=tmp_path).validate(
            BytesIO(make_pdf(password=password)), filename="paper.pdf"
        ):
            pytest.fail("Encrypted PDF was accepted")
    assert caught.value.error_code == "ENCRYPTED_PDF"
    assert list(tmp_path.iterdir()) == []


def test_cleanup_when_the_next_pipeline_step_fails(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="consumer failed"):
        with PDFValidator(temp_root=tmp_path).validate(BytesIO(make_pdf()), filename="paper.pdf"):
            raise RuntimeError("consumer failed")
    assert list(tmp_path.iterdir()) == []


def test_cleanup_after_an_input_read_error(tmp_path: Path) -> None:
    class FailingStream(BytesIO):
        def read(self, size: int = -1) -> bytes:
            if self.tell() >= 5:
                raise OSError("input interrupted")
            return super().read(size)

    with pytest.raises(OSError, match="input interrupted"):
        with PDFValidator(temp_root=tmp_path).validate(
            FailingStream(make_pdf()), filename="paper.pdf"
        ):
            pytest.fail("Interrupted stream was accepted")
    assert list(tmp_path.iterdir()) == []


def test_non_seekable_stream_with_short_reads_is_supported(tmp_path: Path) -> None:
    class ShortStream(BytesIO):
        def read(self, size: int = -1) -> bytes:
            return super().read(min(size, 2))

        def seek(self, offset: int, whence: int = 0) -> int:
            raise UnsupportedOperation("stream cannot seek")

    data = make_pdf()
    with PDFValidator(temp_root=tmp_path).validate(ShortStream(data), filename="paper.pdf") as pdf:
        assert pdf.path.read_bytes() == data


def test_lower_configured_limits_are_enforced(tmp_path: Path) -> None:
    validator = PDFValidator(max_upload_mb=1, max_pdf_pages=2, temp_root=tmp_path)
    for data, code in (
        (padded_pdf(MEBIBYTE + 1), "FILE_TOO_LARGE"),
        (make_pdf(3), "PDF_PAGE_LIMIT_EXCEEDED"),
    ):
        with pytest.raises(PDFValidationError) as caught:
            with validator.validate(BytesIO(data), filename="paper.pdf"):
                pytest.fail("Configured limit was bypassed")
        assert caught.value.error_code == code
    assert list(tmp_path.iterdir()) == []


def test_original_file_is_unchanged(tmp_path: Path) -> None:
    original = tmp_path / "original.pdf"
    data = make_pdf()
    original.write_bytes(data)
    with original.open("rb") as source:
        with PDFValidator(temp_root=tmp_path).validate(source, filename=original.name) as pdf:
            assert pdf.path != original
    assert original.read_bytes() == data
    assert list(tmp_path.iterdir()) == [original]


def test_parser_error_does_not_expose_document_content_or_path(tmp_path: Path) -> None:
    with pytest.raises(PDFValidationError) as caught:
        with PDFValidator(temp_root=tmp_path).validate(
            BytesIO(b"%PDF-1.7\nPRIVATE_DOCUMENT_SENTINEL\n%%EOF"), filename="private.pdf"
        ):
            pytest.fail("Malformed file was accepted")
    assert "PRIVATE_DOCUMENT_SENTINEL" not in str(caught.value)
    assert str(tmp_path) not in str(caught.value)
