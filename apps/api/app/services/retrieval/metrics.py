"""Retrieval metrics and out-of-corpus similarity calibration."""

from collections.abc import Sequence
from math import ceil, isfinite

PageRef = tuple[str, int]
RankedPages = Sequence[PageRef]


def compute_retrieval_metrics(
    rankings: Sequence[tuple[RankedPages, set[PageRef]]], *, k: int = 5
) -> dict[str, float]:
    if k < 1 or not rankings:
        raise ValueError("Metrics require a positive k and at least one answerable query.")

    recalls: list[float] = []
    precisions: list[float] = []
    reciprocal_ranks: list[float] = []
    for ranked_pages, relevant_pages in rankings:
        if not relevant_pages:
            raise ValueError("Every answerable query must have page ground truth.")
        top_pages = ranked_pages[:k]
        relevant_hits = [page in relevant_pages for page in top_pages]
        recall_hits = len({page for page in top_pages if page in relevant_pages})
        recalls.append(recall_hits / len(relevant_pages))
        precisions.append(sum(relevant_hits) / k)
        reciprocal_ranks.append(
            next((1.0 / rank for rank, hit in enumerate(relevant_hits, start=1) if hit), 0.0)
        )

    return {
        f"recall@{k}": sum(recalls) / len(recalls),
        f"precision@{k}": sum(precisions) / len(precisions),
        "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks),
    }


def calibrate_similarity_threshold(
    out_of_corpus_scores: Sequence[float], *, target_detection: float = 0.9
) -> float:
    if not out_of_corpus_scores or not 0 < target_detection <= 1:
        raise ValueError("Calibration requires scores and a target in (0, 1].")
    if any(not isfinite(score) or not -1 <= score <= 1 for score in out_of_corpus_scores):
        raise ValueError("Cosine similarity scores must be finite values from -1 to 1.")

    required = ceil(len(out_of_corpus_scores) * target_detection)
    return sorted(out_of_corpus_scores)[required - 1]


def out_of_corpus_detection_rate(scores: Sequence[float], threshold: float) -> float:
    if not scores:
        raise ValueError("At least one out-of-corpus score is required.")
    return sum(score <= threshold for score in scores) / len(scores)
