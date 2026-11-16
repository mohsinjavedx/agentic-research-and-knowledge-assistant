from collections.abc import Callable, Iterator, Sequence
from io import BytesIO
from pathlib import Path

import pymupdf
import pytest

from app.services.ingestion.detection import PDFTextDensityDetector
from app.services.ingestion.errors import OCRNotSupportedError, PDFExtractionError
from app.services.ingestion.extraction import PDFMarkdownExtractor
from app.services.ingestion.pipeline import PDFIngestionService
from app.services.ingestion.validation import PDFValidator


@pytest.mark.parametrize(
    ("characters", "rejected"), [(0, True), (49, True), (50, False), (51, False)]
)
def test_character_threshold_is_strictly_below_fifty(characters: int, rejected: bool) -> None:
    detector = PDFTextDensityDetector()
    if rejected:
        with pytest.raises(OCRNotSupportedError):
            detector.check(["x" * characters], page_count=1)
    else:
        report = detector.check(["x" * characters], page_count=1)
        assert report.text_char_counts == (characters,)
        assert report.low_text_page_numbers == ()


@pytest.mark.parametrize(
    ("total", "low", "rejected"),
    [
        (5, 4, False),
        (5, 5, True),
        (10, 8, False),
        (10, 9, True),
        (100, 80, False),
        (100, 81, True),
        (3, 1, False),
    ],
)
def test_low_text_fraction_uses_the_whole_document_and_strict_percentage(
    total: int,
    low: int,
    rejected: bool,
) -> None:
    pages = [""] * low + ["x" * 50] * (total - low)
    if rejected:
        with pytest.raises(OCRNotSupportedError) as caught:
            PDFTextDensityDetector().check(pages, page_count=total)
        assert caught.value.total_pages == total
        assert caught.value.status == "failed"
        assert caught.value.status_code == 422
    else:
        report = PDFTextDensityDetector().check(pages, page_count=total)
        assert report.low_text_page_numbers == tuple(range(1, low + 1))
        assert len(report.text_char_counts) == total


def test_failure_stops_consuming_pages_when_rejection_is_certain() -> None:
    def pages() -> Iterator[str]:
        for _ in range(9):
            yield ""
        pytest.fail("Page 10 must not be read after 9/10 pages already failed the threshold")

    with pytest.raises(OCRNotSupportedError) as caught:
        PDFTextDensityDetector().check(pages(), page_count=10)
    assert caught.value.checked_pages == 9
    assert caught.value.page_number == 9


def test_whitespace_and_control_characters_do_not_inflate_density() -> None:
    with pytest.raises(OCRNotSupportedError):
        PDFTextDensityDetector().check(["x" * 49 + " \n\t\r\x00" * 100], page_count=1)


def test_printable_unicode_is_counted_without_modifying_input() -> None:
    text = "\u00e9 " * 50
    report = PDFTextDensityDetector().check([text], page_count=1)
    assert report.text_char_counts == (50,)
    assert text == "\u00e9 " * 50


def test_configured_thresholds_are_used() -> None:
    detector = PDFTextDensityDetector(min_text_chars_per_page=10, max_low_text_page_percent=50)
    report = detector.check(["", "x" * 10], page_count=2)
    assert report.low_text_page_numbers == (1,)
    assert report.min_text_chars_per_page == 10
    with pytest.raises(OCRNotSupportedError):
        detector.check(["", "", "x" * 10], page_count=3)


@pytest.mark.parametrize(
    "options",
    [
        {"min_text_chars_per_page": 0},
        {"min_text_chars_per_page": 10001},
        {"max_low_text_page_percent": -1},
        {"max_low_text_page_percent": 100},
    ],
)
def test_invalid_policy_cannot_disable_all_text_checks(options: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        PDFTextDensityDetector(**options)


@pytest.mark.parametrize(("texts", "count"), [(["x" * 50], 2), (["x" * 50] * 2, 1), ([], 0)])
def test_inconsistent_page_streams_raise_extraction_error(texts: list[str], count: int) -> None:
    with pytest.raises(PDFExtractionError) as caught:
        PDFTextDensityDetector().check(texts, page_count=count)
    assert caught.value.error_code == "PDF_EXTRACTION_FAILED"


@pytest.fixture
def scanned_pdf() -> Callable[[Sequence[bool]], bytes]:
    """True pages have real-looking raster text but no extractable text layer."""

    def build(pattern: Sequence[bool]) -> bytes:
        with pymupdf.open() as document:
            for index, scanned in enumerate(pattern):
                with pymupdf.open() as source:
                    original = source.new_page(width=612, height=792)
                    original.insert_text(
                        (50, 100),
                        f"Research evidence on source page {index + 1}.\n"
                        "Supporting observations make the text sufficiently detailed.",
                        fontsize=12,
                    )
                    page = document.new_page(width=612, height=792)
                    if scanned:
                        page.insert_image(page.rect, stream=original.get_pixmap().tobytes("png"))
                    else:
                        # A separate page keeps its original native text objects.
                        document.delete_page(document.page_count - 1)
                        document.insert_pdf(source)
            return document.tobytes()

    return build


def test_rasterized_pdf_fails_before_layout_analysis_and_cleans_up(
    tmp_path: Path,
    scanned_pdf: Callable[[Sequence[bool]], bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> None:
        pytest.fail("Scanned input must fail before layout analysis or OCR")

    monkeypatch.setattr("app.services.ingestion.extraction.pymupdf4llm.to_markdown", fail_if_called)
    monkeypatch.setattr(PDFMarkdownExtractor, "_remove_text_backgrounds", fail_if_called)
    monkeypatch.setattr("pymupdf.Page.get_textpage_ocr", fail_if_called)
    source = BytesIO(scanned_pdf([True] * 10))
    service = PDFIngestionService(validator=PDFValidator(temp_root=tmp_path))
    with pytest.raises(OCRNotSupportedError) as caught:
        service.extract(source, filename="scan.pdf")
    assert caught.value.error_code == "OCR_NOT_SUPPORTED"
    assert caught.value.checked_pages == 9
    assert list(tmp_path.iterdir()) == []
    assert not source.closed


def test_mixed_pdf_at_exact_eighty_percent_keeps_all_page_numbers(
    tmp_path: Path,
    scanned_pdf: Callable[[Sequence[bool]], bytes],
) -> None:
    service = PDFIngestionService(validator=PDFValidator(temp_root=tmp_path))
    result = service.extract(BytesIO(scanned_pdf([True] * 4 + [False])), filename="mixed.pdf")
    assert [page.page_number for page in result.pages] == [1, 2, 3, 4, 5]
    assert result.text_density.low_text_page_numbers == (1, 2, 3, 4)
    assert result.text_density.text_char_counts[:4] == (0, 0, 0, 0)
    assert result.text_density.text_char_counts[4] >= 50
    assert "Research evidence" in result.pages[4].raw_text
    assert list(tmp_path.iterdir()) == []


def test_text_pdf_passes_with_density_metadata(
    tmp_path: Path,
    scanned_pdf: Callable[[Sequence[bool]], bytes],
) -> None:
    result = PDFIngestionService(validator=PDFValidator(temp_root=tmp_path)).extract(
        BytesIO(scanned_pdf([False, False])), filename="paper.pdf"
    )
    assert result.text_density.low_text_page_numbers == ()
    assert all(count >= 50 for count in result.text_density.text_char_counts)


def test_document_with_blank_middle_page_keeps_raw_markdown_and_density(
    tmp_path: Path,
    layout_pdf: Callable[[str], bytes],
) -> None:
    result = PDFIngestionService(validator=PDFValidator(temp_root=tmp_path)).extract(
        BytesIO(layout_pdf("multipage")), filename="paper.pdf"
    )
    assert result.text_density.low_text_page_numbers == (2,)
    assert result.pages[1].raw_text.strip() == ""
