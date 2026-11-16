# Phase 1, step 4: Deterministic normalization

Implemented and verified: 16 November 2026. This step removes recurring page-boundary text from the indexing representation while retaining original Markdown and exact source mappings.

## Implementation

[normalization.py](../../../apps/api/app/services/ingestion/normalization.py) defines `MarkdownNormalizer`, `NormalizedDocument`, `NormalizedPage`, `SourceSpan`, and `RemovedBoundary`.

The normalizer examines the first nonblank line within the first two physical lines, and the last nonblank line within the last three physical lines. A candidate must recur in the same boundary category on at least two pages and at least 60% of all document pages. Matching is deterministic: whitespace and case are canonicalized for comparison, and explicit page counters such as `Page 1 of 17` share a matching key. Arbitrary model/version numbers are not canonicalized.

The comparison rules preserve Markdown headings, tables, fenced code, list items, blockquotes, inline code/math boundaries, and complete prose sentences. A one-page document cannot establish repetition. Rare boundary text is retained. These conservative rules prefer leaving uncertain text in place over deleting evidence.

Only the matched line content is removed from `normalized_text`. Its newline remains as a placeholder. The application does not rewrite `raw_text`, collapse body whitespace, change case, or remove matching strings from interior paragraphs.

## Source mappings

Each normalized page contains:

- `page_number`: one-based physical PDF page number.
- `raw_text`: the original extracted Markdown, unchanged.
- `normalized_text`: the cleaned indexing representation.
- `removed_boundaries`: original character ranges and header/footer classifications.
- `source_spans`: ranges connecting retained normalized characters to original characters.

Offsets count Python Unicode characters, not UTF-8 bytes. Ranges use an inclusive start and exclusive end. `page.raw_span(start, end)` maps a nonempty normalized range back to the original page. A mapped range can include removed boundary text if it spans a deletion; `raw_text` remains an exact source substring while `normalized_text` excludes the removed content.

```python
from app.services.ingestion.normalization import MarkdownNormalizer

normalized = MarkdownNormalizer().normalize(extracted_document)
page = normalized.pages[0]
start, end = page.raw_span(0, len(page.normalized_text))
source_quote = page.raw_text[start:end]
```

Empty normalized pages have no chunks. Source pages and their numbering remain available in the result.

## Pipeline integration

`PDFIngestionService.prepare()` performs validation, density detection, extraction, normalization, and chunking. `extract()` and the CLI's `--extract` mode continue to return original extracted Markdown for inspection.

From `apps/api`:

```powershell
uv run python -m app.services.ingestion.cli 'C:\path\to\paper.pdf' --prepare --output '.\prepared.json'
```

The output contains original extraction data, normalized pages and source mappings, and traceable chunks. It is an explicit local export, with no automatic database indexing. Existing output files are not overwritten.

## Verification

[Normalization tests](../../../apps/api/tests/unit/test_normalization.py) cover repeated headers and variable page counters, Unicode/CRLF offsets, every retained character's source mapping, protected Markdown structures, repeated interior text, single-page/low-support cases, distinct model numbers, and empty pages. Labelled body strings in these fixtures remain intact.

On the supplied 17-page guide, preparation removed 17 boundary lines, left original extraction strings unchanged, and retained complete normalized-text coverage in chunks. This is a regression smoke result, not the representative-corpus 98% retention benchmark.

The normalizer is a deterministic boundary heuristic. Alternating headers or wrapped multi-line boundary text may remain if they do not meet its conservative evidence rules. Raw Markdown is always available for citation display and future rule improvements.

Next: [step 5, Markdown-aware chunking](phase-1-step-5-markdown-aware-chunking.md).
