import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import numpy as np
import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordPiece
from tokenizers.pre_tokenizers import Whitespace
from tokenizers.processors import TemplateProcessing

from app.core.config import load_settings
from app.providers.reranking import RerankerError, TinyBERTReranker, create_reranker
from app.services.retrieval.context import retrieve_context
from app.services.retrieval.dense import RetrievedChunk


def candidates(count: int = 6) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            UUID(int=i + 1),
            UUID(int=100),
            1,
            i,
            "relevant" if i == count - 1 else "irrelevant",
            0.7,
            fusion_score=1 / (61 + i),
        )
        for i in range(count)
    ]


def tokenizer() -> Tokenizer:
    engine = Tokenizer(
        WordPiece(
            {
                "[PAD]": 0,
                "[UNK]": 1,
                "[CLS]": 2,
                "[SEP]": 3,
                "query": 4,
                "irrelevant": 5,
                "relevant": 6,
            },
            unk_token="[UNK]",
        )
    )
    engine.pre_tokenizer = Whitespace()
    engine.post_processor = TemplateProcessing(
        single="[CLS] $A [SEP]",
        pair="[CLS] $A [SEP] $B:1 [SEP]:1",
        special_tokens=[("[CLS]", 2), ("[SEP]", 3)],
    )
    engine.enable_truncation(max_length=512, strategy="only_second")
    return engine


def test_disabled_reranker_never_downloads_or_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*args: object, **kwargs: object) -> None:
        pytest.fail("disabled reranking loaded an artifact")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", unexpected)
    settings = load_settings().model_copy(update={"enable_reranker": False})
    assert create_reranker(settings) is None
    lazy = TinyBERTReranker()
    assert lazy.rerank("query", []) == []
    lazy.close()


def test_pair_scoring_batches_truncates_and_preserves_identity() -> None:
    calls = []

    class Session:
        def run(self, outputs, inputs):
            calls.append(inputs)
            return [((inputs["input_ids"] == 6).any(axis=1)).astype(float)[:, None]]

    reranker = TinyBERTReranker()
    reranker._session = Session()
    reranker._tokenizer = tokenizer()
    rows = candidates()
    rows[-1] = replace(rows[-1], text="relevant " * 900)
    ranked = reranker.rerank("query", rows)
    assert ranked[0].chunk_id == rows[-1].chunk_id
    assert [len(call["input_ids"]) for call in calls] == [4, 2]
    assert max(call["input_ids"].shape[1] for call in calls) == 512
    assert ranked[0].text == rows[-1].text
    assert ranked[0].cosine_similarity == rows[-1].cosine_similarity
    assert ranked[0].fusion_score == rows[-1].fusion_score
    assert ranked[0].rerank_score == 1
    assert [row.chunk_id for row in ranked[1:]] == [row.chunk_id for row in rows[:-1]]


@pytest.mark.parametrize("logits", [np.array([[np.nan]]), np.zeros((2, 1))])
def test_invalid_neural_output_is_rejected(logits: np.ndarray) -> None:
    reranker = TinyBERTReranker()
    reranker._tokenizer = tokenizer()
    reranker._session = SimpleNamespace(run=lambda *args: [logits])
    with pytest.raises(RerankerError):
        reranker.rerank("query", candidates(1))


def test_reranker_failure_keeps_original_ranks_and_reports_fallback(monkeypatch) -> None:
    rows = candidates(20)
    monkeypatch.setattr(
        "app.services.retrieval.context.retrieve_evidence", AsyncMock(return_value=rows)
    )

    class Broken:
        def rerank(self, question, evidence):
            raise RerankerError("RERANKER_INFERENCE_FAILED")

    settings = load_settings().model_copy(
        update={"enable_reranker": True, "enable_context_expansion": False}
    )
    result = asyncio.run(
        retrieve_context(
            None,
            [1.0] + [0.0] * 383,
            "query",
            [UUID(int=100)],
            settings,
            top_k=5,
            reranker=Broken(),
        )
    )
    assert [row.chunk_id for row in result.ranked] == [row.chunk_id for row in rows[:5]]
    assert result.reranking_applied is False
    assert result.reranker_error == "RERANKER_INFERENCE_FAILED"
