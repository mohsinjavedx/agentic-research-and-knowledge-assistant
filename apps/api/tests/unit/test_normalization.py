import pytest

from app.services.ingestion.normalization import MarkdownNormalizer
from tests.support import extracted_document


def test_repeated_headers_and_numbered_footers_are_removed_only_from_normalized_text() -> None:
    texts = [
        f"Research Journal\n\n# Results\n\nBody evidence {number} remains intact.\n\n"
        f"Page {number} of 3\n\n"
        for number in range(1, 4)
    ]
    source = extracted_document(*texts)
    result = MarkdownNormalizer().normalize(source)
    for index, page in enumerate(result.pages, start=1):
        assert page.raw_text == texts[index - 1]
        assert source.pages[index - 1].raw_text == texts[index - 1]
        assert "Research Journal" not in page.normalized_text
        assert f"Page {index} of 3" not in page.normalized_text
        assert f"Body evidence {index} remains intact." in page.normalized_text
        assert "# Results" in page.normalized_text
        assert {boundary.kind for boundary in page.removed_boundaries} == {"header", "footer"}
    assert MarkdownNormalizer().normalize(source) == result


def test_source_map_recovers_each_retained_character_with_crlf_and_unicode() -> None:
    source = extracted_document(
        *[
            f"Journal\r\n\r\nEvidence caf\u00e9 \U0001f52c {number}.\r\n\r\nPage {number}\r\n"
            for number in range(1, 4)
        ]
    )
    for page in MarkdownNormalizer().normalize(source).pages:
        for index, char in enumerate(page.normalized_text):
            start, end = page.raw_span(index, index + 1)
            assert page.raw_text[start:end] == char
        start = page.normalized_text.index("Evidence")
        end = start + len(f"Evidence caf\u00e9 \U0001f52c {page.page_number}.")
        raw_start, raw_end = page.raw_span(start, end)
        assert page.raw_text[raw_start:raw_end] == page.normalized_text[start:end]
        with pytest.raises(ValueError):
            page.raw_span(0, 0)


@pytest.mark.parametrize(
    "text",
    [
        "# Methods\n\nRepeated body.\n\n# References\n",
        "```text\nResearch Journal\nPage 1\n```\n",
        "| Model | Value |\n| --- | --- |\n| Repeated | 7 |\n",
        "1. Important repeated result\n\nA unique body.\n",
    ],
)
def test_markdown_structure_is_never_removed_as_running_chrome(text: str) -> None:
    for page in MarkdownNormalizer().normalize(extracted_document(text, text, text)).pages:
        assert page.normalized_text == text
        assert page.removed_boundaries == ()


def test_single_page_and_unsupported_boundary_candidates_are_unchanged() -> None:
    text = "Research Journal\n\nUnique paper body.\n\nPage 1\n"
    assert MarkdownNormalizer().normalize(extracted_document(text)).pages[0].normalized_text == text
    result = MarkdownNormalizer().normalize(
        extracted_document(
            "Rare heading\n\nBody alpha.\n\nFooter alpha\n",
            "Rare heading\n\nBody beta.\n\nFooter beta\n",
            "Different heading\n\nBody gamma.\n\nFooter gamma\n",
            "Another heading\n\nBody delta.\n\nFooter delta\n",
        )
    )
    assert all(not page.removed_boundaries for page in result.pages)


def test_identical_text_in_the_body_is_kept() -> None:
    result = MarkdownNormalizer().normalize(
        extracted_document(
            *[
                f"Journal\n\n# Section {number}\n\nJournal\n\nEvidence {number}.\n\nPage {number}\n"
                for number in range(1, 4)
            ]
        )
    )
    for page in result.pages:
        assert page.normalized_text.count("Journal") == 1


def test_distinct_model_numbers_are_not_normalized_into_a_repeated_header() -> None:
    texts = [f"Model {number}\n\nEvidence {number}.\n" for number in (7, 8, 9)]
    result = MarkdownNormalizer().normalize(extracted_document(*texts))
    assert [page.normalized_text for page in result.pages] == texts


def test_empty_pages_have_valid_empty_mappings() -> None:
    result = MarkdownNormalizer().normalize(extracted_document("", "\n\n"))
    assert result.pages[0].source_spans == ()
    assert result.pages[1].normalized_text == "\n\n"
