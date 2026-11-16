import json

import httpx
import numpy as np
import pytest
from tokenizers import Tokenizer, models, pre_tokenizers, processors

from app.core.config import Settings
from app.providers.embeddings import (
    APIEmbeddingProvider,
    BGETokenizer,
    EmbeddingInputTooLong,
    EmbeddingProviderError,
    LocalBGEProvider,
)
from app.services.indexing.preparation import embedding_chunker
from app.services.ingestion.normalization import MarkdownNormalizer
from tests.support import extracted_document


@pytest.fixture
def tokenizer() -> BGETokenizer:
    engine = Tokenizer(
        models.WordLevel({"[UNK]": 0, "[CLS]": 1, "[SEP]": 2, "a": 3}, unk_token="[UNK]")
    )
    engine.pre_tokenizer = pre_tokenizers.Whitespace()
    engine.post_processor = processors.TemplateProcessing(
        single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 1), ("[SEP]", 2)]
    )
    return BGETokenizer(engine)


def vector(first: float = 3, second: float = 4) -> list[float]:
    return [first, second] + [0.0] * 382


def test_local_provider_uses_cls_pooling_and_l2_normalization(tokenizer: BGETokenizer) -> None:
    class Session:
        def run(self, names: object, inputs: dict[str, np.ndarray]) -> list[np.ndarray]:
            batch, length = inputs["input_ids"].shape
            hidden = np.ones((batch, length, 384), dtype=np.float32) * 100
            hidden[:, 0, :] = vector()
            return [hidden]

    provider = LocalBGEProvider(tokenizer=tokenizer)
    provider._session = Session()
    result = provider.embed_documents(["a", "a a"])
    assert len(result) == 2
    assert result[0][:2] == pytest.approx([0.6, 0.8])
    assert result[0][2:] == [0.0] * 382
    assert provider.embed_query("a") == result[0]


def test_hosted_provider_orders_rows_and_prefixes_only_queries(tokenizer: BGETokenizer) -> None:
    requests: list[dict] = []

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        rows = [{"index": i, "embedding": vector(i + 1, 0)} for i in range(len(payload["input"]))]
        return httpx.Response(
            200, json={"data": list(reversed(rows)), "model": "BAAI/bge-small-en-v1.5"}
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = APIEmbeddingProvider(
            url="https://embeddings.example/v1/embeddings",
            api_key="private-key",
            tokenizer=tokenizer,
            client=client,
            batch_size=2,
        )
        assert provider.embed_documents(["a", "a a", "a a a"]) == [vector(1, 0)] * 3
        assert provider.embed_query("a") == vector(1, 0)
    assert requests[0]["input"] == ["a", "a a"]
    assert requests[1]["input"] == ["a a a"]
    assert requests[2]["input"] == ["Represent this sentence for searching relevant passages: a"]


@pytest.mark.parametrize(
    "bad", [[], [0.0] * 383, [0.0] * 384, [float("nan")] * 384, [float("inf")] * 384, [True] * 384]
)
def test_hosted_rejects_invalid_vectors(tokenizer: BGETokenizer, bad: list) -> None:
    content = json.dumps({"data": [{"index": 0, "embedding": bad}]})
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=content))
    ) as client:
        provider = APIEmbeddingProvider(
            url="https://example.test/embeddings", api_key="key", tokenizer=tokenizer, client=client
        )
        with pytest.raises(EmbeddingProviderError):
            provider.embed_documents(["a"])


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"index": 1, "embedding": vector()}],
        [{"index": 0, "embedding": vector()}, {"index": 0, "embedding": vector()}],
    ],
)
def test_hosted_rejects_missing_duplicate_or_out_of_range_rows(
    tokenizer: BGETokenizer, rows: list
) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": rows}))
    ) as client:
        provider = APIEmbeddingProvider(
            url="https://example.test/embeddings", api_key="key", tokenizer=tokenizer, client=client
        )
        with pytest.raises(EmbeddingProviderError):
            provider.embed_documents(["a"])


def test_http_failure_is_sanitized(tokenizer: BGETokenizer) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(500, text="PRIVATE_KEY AND PDF TEXT")
        )
    ) as client:
        provider = APIEmbeddingProvider(
            url="https://example.test/embeddings",
            api_key="PRIVATE_KEY",
            tokenizer=tokenizer,
            client=client,
        )
        with pytest.raises(EmbeddingProviderError) as caught:
            provider.embed_documents(["PDF TEXT"])
        assert "PRIVATE_KEY" not in str(caught.value)
        assert "PDF TEXT" not in str(caught.value)
        assert caught.value.__suppress_context__


def test_oversized_and_empty_inputs_do_not_load_the_model(tokenizer: BGETokenizer) -> None:
    provider = LocalBGEProvider(tokenizer=tokenizer)
    assert provider.embed_documents([]) == []
    with pytest.raises(EmbeddingInputTooLong):
        provider.embed_documents(["a " * 511])
    with pytest.raises(EmbeddingProviderError):
        provider.embed_query(" ")
    assert provider._session is None


def test_embedding_chunks_fit_actual_tokenizer_and_keep_exact_source_coverage(
    tokenizer: BGETokenizer,
) -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://a:b@localhost/test",
        embedding_provider="local",
        embedding_model="BAAI/bge-small-en-v1.5",
        llm_provider="local",
    )
    provider = LocalBGEProvider(tokenizer=tokenizer)
    source = extracted_document("# Heading\n\n" + "a " * 1600)
    document = MarkdownNormalizer().normalize(source)
    from uuid import uuid4

    chunks = embedding_chunker(settings, provider).split(document, document_id=uuid4())
    covered: set[int] = set()
    assert len(chunks) >= 3
    for chunk in chunks:
        text = chunk.normalized_text
        assert provider.tokenizer.count(text, include_special_tokens=True) <= 512
        assert source.pages[0].raw_text[chunk.char_start : chunk.char_end] == chunk.raw_text
        start, end = chunk.metadata["normalized_char_start"], chunk.metadata["normalized_char_end"]
        covered.update(range(int(start), int(end)))
        assert chunk.metadata["tokenizer"] != "cl100k_base"
    assert all(
        i in covered
        for i, char in enumerate(document.pages[0].normalized_text)
        if not char.isspace()
    )


def test_protected_oversized_code_is_not_truncated(tokenizer: BGETokenizer) -> None:
    from uuid import uuid4

    from app.services.chunking.splitter import MarkdownChunker

    source = extracted_document("```text\n" + "a\n" * 700 + "```\n")
    document = MarkdownNormalizer().normalize(source)
    chunker = MarkdownChunker(
        min_tokens=300,
        max_tokens=510,
        overlap_tokens=50,
        count_tokens=tokenizer.count,
        tokenizer_name="BGE",
    )
    chunks = chunker.split(document, document_id=uuid4())
    assert len(chunks) == 1
    assert chunks[0].metadata["oversized_atomic"]
    with pytest.raises(EmbeddingInputTooLong):
        LocalBGEProvider(tokenizer=tokenizer).embed_documents([chunks[0].normalized_text])
