import socket
from uuid import UUID, uuid4

import pytest

from app.services.chunking.markdown import markdown_blocks
from app.services.chunking.splitter import MarkdownChunker
from app.services.chunking.tokenizer import _encoding, token_count
from app.services.ingestion.normalization import MarkdownNormalizer
from tests.support import extracted_document


def assert_coverage(source: str, chunks: tuple, page: int = 1) -> None:
    covered: set[int] = set()
    for chunk in chunks:
        if chunk.page_start != page:
            continue
        start = chunk.metadata["normalized_char_start"]
        end = chunk.metadata["normalized_char_end"]
        assert source[start:end] == chunk.normalized_text
        covered.update(range(start, end))
    assert all(
        index in covered for index, character in enumerate(source) if not character.isspace()
    )


def test_offline_tokenizer_handles_uploaded_special_tokens_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        pytest.fail("Token counting must never use the network")

    _encoding.cache_clear()
    monkeypatch.setattr(socket, "create_connection", fail)
    assert token_count("Hello world") == 2
    assert token_count("<|endoftext|> is document data") > 1
    assert token_count("\u4e2d\u6587 \U0001f52c caf\u00e9") > 0


def test_normal_prose_uses_real_token_budgets_overlap_and_exact_provenance() -> None:
    text = "\n\n".join(
        f"Paragraph {index}. " + "Evidence supports the measured research result. " * 45
        for index in range(12)
    )
    document = MarkdownNormalizer().normalize(extracted_document(text))
    identity = uuid4()
    chunks = MarkdownChunker().split(document, document_id=identity)
    assert len(chunks) > 3
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.document_id == str(identity) for chunk in chunks)
    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.raw_text
        assert chunk.page_start == chunk.page_end == 1
        assert UUID(chunk.id)
        assert chunk.metadata["token_count"] == token_count(chunk.normalized_text)
        assert token_count(chunk.normalized_text) <= 800
    assert all(600 <= token_count(chunk.normalized_text) <= 800 for chunk in chunks[:-1])
    for previous, current in zip(chunks, chunks[1:], strict=False):
        overlap = text[current.char_start : previous.char_end]
        assert 98 <= token_count(overlap) <= 100
        assert current.char_end > previous.char_end
    assert_coverage(text, chunks)
    assert MarkdownChunker().split(document, document_id=identity) == chunks
    assert MarkdownChunker().split(document, document_id=uuid4())[0].id != chunks[0].id


@pytest.mark.parametrize("kind", ["table", "code"])
def test_oversized_atomic_blocks_are_whole_and_prose_is_not_lost(kind: str) -> None:
    if kind == "table":
        atomic = "| Metric | Value |\n| --- | --- |\n" + "".join(
            f"| Row {index} | measured evidence {index} |\n" for index in range(160)
        )
    else:
        atomic = "```python\n" + "print('source evidence')\n" * 250 + "```\n"
    text = "Introductory evidence. " * 210 + "\n\n" + atomic + "\n" + "Final evidence. " * 230
    document = MarkdownNormalizer().normalize(extracted_document(text))
    chunks = MarkdownChunker().split(document, document_id=uuid4())
    whole = [chunk for chunk in chunks if atomic.strip() in chunk.normalized_text]
    assert len(whole) == 1
    assert whole[0].metadata["oversized_atomic"] is True
    assert len(chunks) < 15
    assert_coverage(text, chunks)


def test_embedding_mode_splits_oversized_tables_at_row_boundaries() -> None:
    rows = [f"| Row {index} | measured evidence {index} |" for index in range(160)]
    table = "| Metric | Value |\n| --- | --- |\n" + "\n".join(rows)
    document = MarkdownNormalizer().normalize(extracted_document(table))
    chunks = MarkdownChunker(
        min_tokens=80,
        max_tokens=120,
        overlap_tokens=20,
        split_oversized_atomic=True,
    ).split(document, document_id=uuid4())

    assert len(chunks) > 1
    assert all(token_count(chunk.normalized_text) <= 120 for chunk in chunks)
    assert all(chunk.metadata["oversized_atomic"] is False for chunk in chunks)
    assert all(any(row in chunk.normalized_text for chunk in chunks) for row in rows)
    assert_coverage(table, chunks)


def test_regular_table_fits_as_a_single_block_with_no_partial_overlap() -> None:
    table = "| Model | Score |\n| --- | --- |\n" + "| Baseline | 0.80 |\n" * 10
    text = "Before the table. " * 30 + "\n\n" + table + "\nAfter the table. " * 30
    document = MarkdownNormalizer().normalize(extracted_document(text))
    chunks = MarkdownChunker(min_tokens=50, max_tokens=120, overlap_tokens=20).split(
        document, document_id=uuid4()
    )
    assert sum(table.strip() in chunk.normalized_text for chunk in chunks) == 1
    assert_coverage(text, chunks)


def test_unicode_long_words_and_page_boundaries_have_complete_source_spans() -> None:
    texts = ["\U0001f52c\u4e2d\u6587caf\u00e9" * 100, "antidisestablishmentarianism" * 100]
    document = MarkdownNormalizer().normalize(extracted_document(*texts))
    chunks = MarkdownChunker(min_tokens=25, max_tokens=40, overlap_tokens=5).split(
        document, document_id=uuid4()
    )
    for chunk in chunks:
        assert chunk.raw_text == texts[chunk.page_start - 1][chunk.char_start : chunk.char_end]
        assert token_count(chunk.normalized_text) <= 40
    for index, text in enumerate(texts, start=1):
        assert_coverage(text, chunks, index)


def test_removed_running_text_is_absent_from_indexed_chunks_but_offsets_reference_raw_pages() -> (
    None
):
    texts = [
        f"Journal\n\n# Results {index}\n\n" + "Scientific evidence. " * 80 + f"\n\nPage {index}\n"
        for index in range(1, 4)
    ]
    document = MarkdownNormalizer().normalize(extracted_document(*texts))
    chunks = MarkdownChunker(min_tokens=30, max_tokens=60, overlap_tokens=10).split(
        document, document_id=uuid4()
    )
    for chunk in chunks:
        assert "Journal" not in chunk.normalized_text
        assert "Page " not in chunk.normalized_text
        assert texts[chunk.page_start - 1][chunk.char_start : chunk.char_end] == chunk.raw_text
    for page in document.pages:
        assert_coverage(page.normalized_text, chunks, page.page_number)


def test_heading_boundaries_and_fenced_table_text_are_identified_without_changes() -> None:
    text = "# Methods\n\nEvidence.\n\n```text\n| Not a table |\n| --- |\n```\n\n# Results\n"
    blocks = markdown_blocks(text)
    assert [block.kind for block in blocks if block.kind != "blank"] == [
        "heading",
        "paragraph",
        "code",
        "heading",
    ]
    assert "".join(text[block.start : block.end] for block in blocks) == text


@pytest.mark.parametrize(
    "options",
    [
        {"min_tokens": 100, "max_tokens": 50},
        {"overlap_tokens": 600},
        {"overlap_tokens": -1},
    ],
)
def test_invalid_chunk_budgets_fail(options: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        MarkdownChunker(**options)
