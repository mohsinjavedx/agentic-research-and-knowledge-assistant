"""Fit complete sources/groups within a conservative model input budget."""

import json
from collections.abc import Callable, Sequence
from itertools import groupby
from typing import Any

from openai.types.chat import ChatCompletionMessageParam

from app.services.chunking.tokenizer import token_count
from app.services.generation.evidence import EvidencePassage, focus_evidence
from app.services.generation.prompt import build_messages
from app.services.retrieval.dense import RetrievedChunk


def pack_context(
    question: str,
    evidence: Sequence[RetrievedChunk],
    *,
    input_budget: int,
    schema_factory: Callable[[int], dict[str, Any]],
) -> tuple[list[ChatCompletionMessageParam], list[EvidencePassage]]:
    selected: list[EvidencePassage] = []
    messages: list[ChatCompletionMessageParam] = []
    passages = focus_evidence(question, evidence)
    for _, unit in groupby(
        passages, key=lambda row: row.source.context_group or row.source.chunk_id
    ):
        trial = [*selected, *unit]
        candidate = build_messages(question, [row.prompt_chunk() for row in trial])
        tokens = token_count(json.dumps(candidate, ensure_ascii=False)) + token_count(
            json.dumps(schema_factory(len(trial)))
        )
        # cl100k_base estimates a different provider tokenizer/template. Include
        # schema cost, 25% headroom and 64 template tokens; never clip a source.
        if (tokens * 5 + 3) // 4 + 64 <= input_budget:
            messages, selected = candidate, trial
    return messages, selected
