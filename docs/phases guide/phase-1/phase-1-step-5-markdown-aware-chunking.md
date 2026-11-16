# Phase 1, step 5: Markdown-aware chunking

Implemented and verified: 16 November 2026. The preparation pipeline now creates typed chunks whose offsets reference exact source-page Markdown.

## Source files

| File | Purpose |
| --- | --- |
| [markdown.py](../../../apps/api/app/services/chunking/markdown.py) | Detect ATX headings, paragraphs, blank lines, pipe tables, and fenced code without modifying characters. |
| [splitter.py](../../../apps/api/app/services/chunking/splitter.py) | Select token-bounded spans with structural boundaries and overlap, then map them to original pages. |
| [tokenizer.py](../../../apps/api/app/services/chunking/tokenizer.py) | Count real `cl100k_base` tokens using bundled vocabulary with checksum verification. |
| [assets](../../../apps/api/app/services/chunking/assets/README.md) | Vocabulary provenance, fixed encoding configuration, and upstream MIT license. |
| [chunks.py](../../../apps/api/app/schemas/chunks.py) | Pydantic `ChunkSchema` contract and provenance validation. |
| [pipeline.py](../../../apps/api/app/services/ingestion/pipeline.py) | `PreparedDocument` and the combined `prepare()` operation. |

## Splitting policy

Defaults target 600-800 tokens with up to 100 tokens of overlap. The chunker first prefers section/paragraph boundaries, then sentence boundaries, whitespace, and finally Unicode character boundaries for indivisible long words. It verifies the actual token count of selected text.

Tables and fenced code are atomic. If one cannot fit with preceding overlap, the overlap is dropped before that block rather than emitting repeated prefixes. A block larger than the maximum is emitted whole and flagged with `oversized_atomic: true`. A suffix inside such a block is not copied into another chunk as partial overlap.

Chunks stay within a single source page, so `page_start == page_end`. This avoids ambiguous cross-page offsets. Short pages and page/section tails can be smaller than 600 tokens. Atomic tables/code can be larger than 800. The target is not a requirement to pad short content or cut a table to an exact size. Normal prose uses up to 100-token overlap within the same page; page boundaries and atomic-block protection can reduce that overlap.

The vocabulary is bundled at about 1.7 MB so token counting works without network downloads or an external cache. Its SHA-256 is verified when first loaded. This is tokenizer vocabulary data, not neural model weights. Special-token-looking strings inside a PDF are encoded as ordinary document data.

## Chunk contract

Each chunk includes:

```text
id, document_id, chunk_index
raw_text, normalized_text
page_start, page_end, char_start, char_end
metadata
```

`char_start` and `char_end` index into the original extracted Markdown of the source page. The invariant is:

```python
source_page.raw_text[chunk.char_start:chunk.char_end] == chunk.raw_text
```

The Pydantic schema checks positive page numbers, ordered nonempty offsets, raw-text length, and single-page provenance. `chunk_index` is continuous across the document, starting at zero.

Metadata includes the real token count, tokenizer name, atomic-overflow flag, and normalized character start/end. Those normalized offsets independently locate `normalized_text` in the cleaned page. Raw source offsets are never calculated from the length of normalized text.

Chunk IDs are stable UUID5 values derived from the document UUID, source page/range, and normalized-text hash. The preparation API accepts an existing document UUID. The standalone CLI derives a reproducible document UUID from the original PDF checksum; a future session-scoped ingestion job should supply its persisted `Document.id` instead.

## Usage

From `apps/api`:

```powershell
uv sync --frozen
uv run python -m app.services.ingestion.cli 'C:\path\to\paper.pdf' --prepare --output '.\prepared.json'
```

Configuration defaults in the root `.env.example`:

```dotenv
CHUNK_MIN_TOKENS=600
CHUNK_MAX_TOKENS=800
CHUNK_OVERLAP_TOKENS=100
```

Typed settings require `0 <= overlap < minimum <= maximum`. The configured minimum and maximum are bounded at 8,000 tokens. Python runtime and type-check configuration now consistently target Python 3.12, matching `.python-version`, CI, and the Docker image.

The CLI exports `status: "prepared"`, document ID, original extraction, normalized pages and mappings, and chunks. `--prepare` and `--extract` are separate modes. This step does not create embeddings or persistent chunk/vector indexes; those belong to Phase 2.

## Verification

[Chunking tests](../../../apps/api/tests/unit/test_chunking.py) cover real token budgets, normal-prose overlap, complete character coverage, stable IDs, different document identities, whole normal and oversized tables, fenced code, Unicode, long unbroken words, page boundaries, normalized/raw offsets, and offline handling of uploaded special-token strings. The CLI preparation test verifies normalization and chunk provenance together.

The supplied guide prepared into 17 chunks from 17 pages. Every chunk's raw range matched its original page, every normalized non-whitespace character was covered, and all token counts matched the tokenizer. No oversized atomic chunk was needed for that sample. The temporary PDF was deleted.

Next: [step 6, crash-safe recovery](phase-1-step-6-crash-safe-recovery.md).
