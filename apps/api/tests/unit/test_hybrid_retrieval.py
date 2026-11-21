import asyncio
from uuid import UUID

from app.services.retrieval.dense import RetrievedChunk
from app.services.retrieval.hybrid import fuse_rankings, retrieve_hybrid


def chunk(index: int, similarity: float = 0.75) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=UUID(int=index),
        document_id=UUID(int=100),
        page_number=index,
        chunk_index=index,
        text=f"Source {index}",
        cosine_similarity=similarity,
    )


def test_fusion_combines_rankings_without_overwriting_cosine_similarity() -> None:
    a, b, c, d = chunk(1, 0.9), chunk(2, 0.7), chunk(3), chunk(4, 0.4)
    results = fuse_rankings([[a, b, c], [b, d, a]], top_k=4)
    assert [item.chunk_id for item in results] == [b.chunk_id, a.chunk_id, d.chunk_id, c.chunk_id]
    assert results[0].cosine_similarity == 0.7
    assert results[0].fusion_score == 1 / 62 + 1 / 61
    assert len({item.chunk_id for item in results}) == 4


def test_duplicate_source_in_one_branch_does_not_gain_an_extra_vote() -> None:
    a, b = chunk(1), chunk(2)
    results = fuse_rankings([[a, a], [b]], top_k=2)
    assert len(results) == 2
    assert results[0].fusion_score == results[1].fusion_score


def test_empty_document_scope_never_runs_a_keyword_query() -> None:
    results = asyncio.run(retrieve_hybrid(object(), [1.0] + [0.0] * 383, "private keyword", []))
    assert results == []
