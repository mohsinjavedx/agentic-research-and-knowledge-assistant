import pytest
from pydantic import ValidationError

from app.schemas.retrieval import SearchRequest
from app.services.retrieval.metrics import (
    calibrate_similarity_threshold,
    compute_retrieval_metrics,
    out_of_corpus_detection_rate,
)


def test_search_request_strips_query_and_rejects_duplicate_document_ids() -> None:
    request = SearchRequest.model_validate(
        {"query": "  find evidence  ", "document_ids": None, "top_k": 5}
    )
    assert request.query == "find evidence"

    with pytest.raises(ValidationError):
        SearchRequest.model_validate({"query": "   "})
    with pytest.raises(ValidationError):
        SearchRequest.model_validate(
            {
                "query": "find evidence",
                "document_ids": ["00000000-0000-0000-0000-000000000001"] * 2,
            }
        )


def test_page_metrics_use_unique_ground_truth_pages_and_top_five_precision() -> None:
    metrics = compute_retrieval_metrics(
        [
            (
                [
                    ("doc-a", 1),
                    ("doc-a", 1),
                    ("doc-b", 2),
                    ("doc-c", 4),
                    ("doc-d", 5),
                ],
                {("doc-a", 1), ("doc-b", 2)},
            )
        ]
    )
    assert metrics == {"recall@5": 1.0, "precision@5": 0.6, "mrr": 1.0}


def test_similarity_cutoff_flags_at_least_target_share_of_out_of_corpus_queries() -> None:
    scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
    threshold = calibrate_similarity_threshold(scores)
    assert threshold == 0.9
    assert out_of_corpus_detection_rate(scores, threshold) == 0.9
