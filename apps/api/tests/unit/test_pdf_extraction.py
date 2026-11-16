from collections.abc import Callable
from dataclasses import FrozenInstanceError
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest

from app.services.ingestion.errors import OCRNotSupportedError, PDFExtractionError
from app.services.ingestion.extraction import PDFMarkdownExtractor
from app.services.ingestion.pipeline import PDFIngestionService
from app.services.ingestion.validation import PDFValidationError, PDFValidator


def service(tmp_path: Path) -> PDFIngestionService:
    return PDFIngestionService(validator=PDFValidator(temp_root=tmp_path))


def test_extracts_markdown_with_source_metadata_and_cleans_up(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
) -> None:
    data = layout_pdf("text")
    source = BytesIO(data)
    result = service(tmp_path).extract(source, filename="paper.pdf")
    assert result.page_count == 1
    assert result.pages[0].page_number == 1
    assert "Evidence stays attached to its source page." in result.pages[0].raw_text
    assert result.checksum == sha256(data).hexdigest()
    assert result.size_bytes == len(data)
    assert result.parser == "pymupdf4llm"
    assert result.parser_version
    assert result.text_density.text_char_counts[0] >= 50
    assert result.text_density.low_text_page_numbers == ()
    assert list(tmp_path.iterdir()) == []
    assert not source.closed
    with pytest.raises(FrozenInstanceError):
        result.pages[0].raw_text = "changed"  # type: ignore[misc]


def test_two_columns_follow_reading_order_instead_of_drawing_order(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
) -> None:
    result = service(tmp_path).extract(BytesIO(layout_pdf("columns")), filename="columns.pdf")
    text = result.pages[0].raw_text
    phrases = ["Left opening", "Left conclusion", "Right opening", "Right conclusion"]
    positions = [text.index(phrase) for phrase in phrases]
    assert positions == sorted(positions), text


@pytest.mark.parametrize("kind", ["table", "shaded_table"])
def test_table_headers_values_and_rows_are_preserved_in_markdown(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    kind: str,
) -> None:
    result = service(tmp_path).extract(BytesIO(layout_pdf(kind)), filename="table.pdf")
    table_lines = [line for line in result.pages[0].raw_text.splitlines() if line.startswith("|")]
    assert any(
        all(value in line for value in ["Model", "Recall", "Latency"]) for line in table_lines
    )
    assert any(
        all(value in line for value in ["Baseline", "0.80", "800 ms"]) for line in table_lines
    )
    assert any(
        all(value in line for value in ["Hybrid", "0.86", "1100 ms"]) for line in table_lines
    )
    assert any("---" in line for line in table_lines), table_lines
    if kind == "shaded_table":
        assert "Shaded evidence must remain beside the table." in result.pages[0].raw_text


def test_shaded_code_blocks_are_extracted_without_modifying_source_bytes(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
) -> None:
    data = layout_pdf("shaded_code")
    source = BytesIO(data)
    result = service(tmp_path).extract(source, filename="code.pdf")
    for value in ("app/main.py", "app/core/config.py", "services/ingestion/"):
        assert value in result.pages[0].raw_text
    assert source.getvalue() == data
    assert list(tmp_path.iterdir()) == []


def test_blank_pages_keep_their_position_without_cross_page_merging(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
) -> None:
    result = service(tmp_path).extract(BytesIO(layout_pdf("multipage")), filename="pages.pdf")
    assert [page.page_number for page in result.pages] == [1, 2, 3]
    assert "First page evidence" in result.pages[0].raw_text
    assert not result.pages[1].raw_text.strip()
    assert "Third page evidence" in result.pages[2].raw_text
    assert "Third page evidence" not in result.pages[0].raw_text


def test_headers_and_footers_are_retained_for_later_normalization(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
) -> None:
    result = service(tmp_path).extract(BytesIO(layout_pdf("headers")), filename="headers.pdf")
    for page in result.pages:
        assert "Research journal running header" in page.raw_text
        assert "Journal footer retained for cleanup" in page.raw_text


def test_image_only_page_is_rejected_without_ocr_or_image_export(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_ocr_runs(*args: object, **kwargs: object) -> None:
        pytest.fail("OCR must not run during text-based extraction")

    monkeypatch.setattr("pymupdf.Page.get_textpage_ocr", fail_if_ocr_runs)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(OCRNotSupportedError) as caught:
        service(tmp_path).extract(BytesIO(layout_pdf("image")), filename="scan.pdf")
    assert caught.value.error_code == "OCR_NOT_SUPPORTED"
    assert caught.value.status == "failed"
    assert list(tmp_path.iterdir()) == []


def test_repeated_extraction_has_stable_raw_markdown(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
) -> None:
    data = layout_pdf("table")
    first = service(tmp_path).extract(BytesIO(data), filename="table.pdf")
    second = service(tmp_path).extract(BytesIO(data), filename="different.pdf")
    assert first == second


def test_invalid_input_never_reaches_the_extractor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> None:
        pytest.fail("Validation must run before extraction")

    monkeypatch.setattr(PDFMarkdownExtractor, "extract", fail_if_called)
    with pytest.raises(PDFValidationError):
        service(tmp_path).extract(BytesIO(b"not a PDF"), filename="paper.pdf")
    assert list(tmp_path.iterdir()) == []


def test_parser_failure_is_sanitized_and_temporary_file_is_removed(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("PRIVATE_CONTENT_SENTINEL /private/temporary/file.pdf")

    monkeypatch.setattr("app.services.ingestion.extraction.pymupdf4llm.to_markdown", fail)
    with pytest.raises(PDFExtractionError) as caught:
        service(tmp_path).extract(BytesIO(layout_pdf("text")), filename="paper.pdf")
    assert caught.value.page_number == 1
    assert caught.value.error_code == "PDF_EXTRACTION_FAILED"
    assert "PRIVATE_CONTENT_SENTINEL" not in str(caught.value)
    assert "temporary/file.pdf" not in str(caught.value)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "response",
    [
        "wrong type",
        [],
        [{"text": None}],
        [{"text": "content", "metadata": {"page": 9}}],
    ],
)
def test_incomplete_or_misnumbered_parser_results_fail_instead_of_losing_pages(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    monkeypatch: pytest.MonkeyPatch,
    response: object,
) -> None:
    monkeypatch.setattr(
        "app.services.ingestion.extraction.pymupdf4llm.to_markdown",
        lambda *args, **kwargs: response,
    )
    with pytest.raises(PDFExtractionError):
        service(tmp_path).extract(BytesIO(layout_pdf("text")), filename="paper.pdf")
    assert list(tmp_path.iterdir()) == []


def test_adapter_preserves_raw_whitespace_and_disables_ocr_and_image_writes(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_text = "\n\n# Header\n\nEvidence.  \n\n"

    def extract(*args: object, **kwargs: object) -> list[dict[str, object]]:
        assert kwargs["ignore_images"] is True
        assert kwargs["margins"] == 0
        assert kwargs["write_images"] is False
        assert kwargs["embed_images"] is False
        return [{"text": raw_text, "metadata": {"page": 1}}]

    monkeypatch.setattr("app.services.ingestion.extraction.pymupdf4llm.to_markdown", extract)
    result = service(tmp_path).extract(BytesIO(layout_pdf("text")), filename="paper.pdf")
    assert result.pages[0].raw_text == raw_text


def test_empty_markdown_for_a_text_page_is_a_parser_failure(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.ingestion.extraction.pymupdf4llm.to_markdown",
        lambda *args, **kwargs: [{"text": "", "metadata": {"page": 1}}],
    )
    with pytest.raises(PDFExtractionError) as caught:
        service(tmp_path).extract(BytesIO(layout_pdf("text")), filename="text.pdf")
    assert caught.value.error_code == "PDF_EXTRACTION_FAILED"
    assert list(tmp_path.iterdir()) == []
