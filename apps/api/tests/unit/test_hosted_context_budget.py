import json
from dataclasses import replace
from uuid import UUID

import pytest

from app.providers.llm import LLMProviderError, OpenAICompatibleLLM
from app.schemas.answers import GroundedResponse
from app.services.chunking.tokenizer import token_count
from app.services.retrieval.dense import RetrievedChunk


def test_hosted_context_is_bounded_and_keeps_adjacent_groups_atomic() -> None:
    provider = OpenAICompatibleLLM(
        base_url="https://example.test/v1",
        api_key="test",
        model="test",
        timeout_seconds=10,
        input_token_budget=3000,
    )
    anchor = RetrievedChunk(
        UUID(int=1), UUID(int=100), 1, 0, "fact " * 650, 0.8, context_group=UUID(int=1)
    )
    neighbor = replace(anchor, chunk_id=UUID(int=2), chunk_index=1, is_adjacent_context=True)
    oversized = replace(
        anchor, chunk_id=UUID(int=3), chunk_index=2, text="oversized " * 5000, context_group=None
    )
    later = replace(
        anchor, chunk_id=UUID(int=4), chunk_index=3, text="Short later fact.", context_group=None
    )
    try:
        messages, passages = provider._messages(
            "What is the fact?", [anchor, neighbor, oversized, later]
        )
        tokens = token_count(json.dumps(messages, ensure_ascii=False)) + token_count(
            json.dumps(GroundedResponse.model_json_schema())
        )
        assert (tokens * 5 + 3) // 4 + 64 <= 3000
        assert [p.source.chunk_id for p in passages] == [
            anchor.chunk_id,
            neighbor.chunk_id,
            later.chunk_id,
        ]
        assert [p.retrieval_index for p in passages] == [0, 1, 3]
        assert passages[0].text == anchor.text and passages[1].text == neighbor.text
        # If only one member would fit, skip the whole pair, then try later evidence.
        provider._input_token_budget = 1600
        _, passages = provider._messages("What is the fact?", [anchor, neighbor, later])
        assert [p.source.chunk_id for p in passages] == [later.chunk_id]
        with pytest.raises(LLMProviderError):
            provider._messages("What is the fact?", [oversized])
    finally:
        provider.close()
