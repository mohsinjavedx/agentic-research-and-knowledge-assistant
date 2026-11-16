"""Use the actual embedding tokenizer while retaining Phase 1 provenance."""

from app.core.config import Settings
from app.providers.embeddings import EmbeddingProvider
from app.services.chunking.splitter import MarkdownChunker


def embedding_chunker(settings: Settings, provider: EmbeddingProvider) -> MarkdownChunker:
    maximum = min(settings.chunk_max_tokens, provider.tokenizer.content_limit)
    minimum = max(1, settings.chunk_min_tokens * maximum // settings.chunk_max_tokens)
    overlap = min(settings.chunk_overlap_tokens, minimum - 1)
    return MarkdownChunker(
        min_tokens=minimum,
        max_tokens=maximum,
        overlap_tokens=overlap,
        count_tokens=provider.tokenizer.count,
        tokenizer_name=provider.tokenizer.name,
    )
