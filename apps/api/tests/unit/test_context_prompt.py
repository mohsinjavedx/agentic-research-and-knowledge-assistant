from uuid import UUID

from app.services.generation.evidence import focus_evidence
from app.services.generation.prompt import build_messages
from app.services.retrieval.dense import RetrievedChunk


def test_logically_merged_context_preserves_entire_chunks_order_and_individual_ids() -> None:
    group = UUID(int=1)
    anchor = RetrievedChunk(
        UUID(int=2),
        UUID(int=100),
        8,
        16,
        "Continuation of the split paragraph.\n\nAdditional fact.",
        0.8,
        context_group=group,
    )
    before = RetrievedChunk(
        UUID(int=1),
        UUID(int=100),
        7,
        15,
        "Opening of the split paragraph.\n\nIts qualifying condition.",
        0.79,
        context_group=group,
        is_adjacent_context=True,
    )
    passages = focus_evidence("What is the additional fact?", [anchor, before])
    assert [row.source.chunk_id for row in passages] == [before.chunk_id, anchor.chunk_id]
    assert passages[0].text == before.text and passages[1].text == anchor.text
    assert [row.retrieval_index for row in passages] == [1, 0]
    prompt = str(build_messages("Question", [row.prompt_chunk() for row in passages])[1]["content"])
    assert "<context-group" in prompt
    assert prompt.index(str(before.chunk_id)) < prompt.index(str(anchor.chunk_id))
    assert 'page="7"' in prompt and 'page="8"' in prompt
