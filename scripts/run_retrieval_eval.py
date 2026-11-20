"""Run the Phase 3 dense-retrieval baseline and calibrate its abstention cutoff."""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import select

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "apps" / "api"))

from app.core.config import load_settings  # noqa: E402
from app.db.models import Document  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.providers.embeddings import create_embedding_provider  # noqa: E402
from app.services.retrieval.dense import search_chunks  # noqa: E402
from app.services.retrieval.metrics import (  # noqa: E402
    calibrate_similarity_threshold,
    compute_retrieval_metrics,
    out_of_corpus_detection_rate,
)

GOLDEN_SET_PATH = REPOSITORY_ROOT / "data" / "eval" / "golden_set.json"
SAMPLE_MANIFEST_PATH = REPOSITORY_ROOT / "data" / "samples" / "manifest.json"
REPORT_PATH = REPOSITORY_ROOT / "data" / "eval" / "retrieval_metrics.json"
TOP_K = 5


def _read_inputs() -> tuple[list[dict[str, Any]], list[UUID]]:
    golden_set = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(SAMPLE_MANIFEST_PATH.read_text(encoding="utf-8"))
    questions = golden_set.get("questions")
    documents = manifest.get("documents")
    if golden_set.get("version") != 1 or manifest.get("version") != 1:
        raise ValueError("Unsupported Phase 3 evaluation data version.")
    if not isinstance(questions, list) or len(questions) != 40:
        raise ValueError("The retrieval golden set must contain exactly 40 questions.")
    if not isinstance(documents, list) or not documents:
        raise ValueError("The sample corpus manifest is empty.")

    sample_ids = [UUID(document["document_id"]) for document in documents]
    sample_page_counts = {
        UUID(document["document_id"]): document["page_count"] for document in documents
    }
    answerable = [item for item in questions if item.get("answerable") is True]
    unanswerable = [item for item in questions if item.get("answerable") is False]
    if len(answerable) != 30 or len(unanswerable) != 10:
        raise ValueError("The golden set must contain 30 answerable and 10 out-of-corpus items.")
    expected_categories = {
        "single_fact": 10,
        "table_lookup": 10,
        "cross_section_synthesis": 10,
        "out_of_corpus": 10,
    }
    categories = {category: 0 for category in expected_categories}
    for item in questions:
        category = item.get("category")
        if category not in categories:
            raise ValueError(f"Unknown evaluation category: {category}")
        categories[category] += 1
        ground_truth = item.get("ground_truth")
        if not isinstance(ground_truth, list):
            raise ValueError(f"Question {item.get('id')} has invalid ground truth.")
        if item["answerable"] and not ground_truth:
            raise ValueError(f"Answerable question {item['id']} needs page ground truth.")
        if not item["answerable"] and ground_truth:
            raise ValueError(f"Out-of-corpus question {item['id']} cannot have ground truth.")
        for reference in ground_truth:
            if (
                UUID(reference["document_id"]) not in sample_ids
                or not 1
                <= reference["page_number"]
                <= sample_page_counts[UUID(reference["document_id"])]
            ):
                raise ValueError(f"Question {item['id']} references an invalid page.")
    if categories != expected_categories:
        raise ValueError("The golden set must have 10 questions in each evaluation category.")
    return questions, sample_ids


async def _run() -> dict[str, Any]:
    questions, sample_ids = _read_inputs()
    settings = load_settings()
    provider = create_embedding_provider(settings)
    database = Database(settings)
    try:
        await database.check()
        async with database.sessions() as session:
            indexed_ids = set(
                (
                    await session.scalars(
                        select(Document.id).where(
                            Document.id.in_(sample_ids),
                            Document.is_sample.is_(True),
                            Document.status == "ready",
                        )
                    )
                ).all()
            )
        if indexed_ids != set(sample_ids):
            raise RuntimeError(
                "The full sample corpus is not indexed. Run "
                "'uv run python -m app.services.indexing.seed_samples' from apps/api."
            )

        await asyncio.to_thread(provider.embed_query, "retrieval evaluation warm-up")
        rankings: list[tuple[list[tuple[str, int]], set[tuple[str, int]]]] = []
        out_of_corpus_scores: list[float] = []
        answerable_scores: list[float] = []
        latencies_ms: list[float] = []
        for item in questions:
            started = perf_counter()
            results = await search_chunks(
                database,
                provider,
                item["question"],
                sample_ids,
                top_k=TOP_K,
            )
            latencies_ms.append((perf_counter() - started) * 1000)
            maximum_similarity = results[0].cosine_similarity if results else -1.0
            if item["answerable"]:
                answerable_scores.append(maximum_similarity)
                ranked_pages = [(str(result.document_id), result.page_number) for result in results]
                relevant_pages = {
                    (str(UUID(reference["document_id"])), reference["page_number"])
                    for reference in item["ground_truth"]
                }
                rankings.append((ranked_pages, relevant_pages))
            else:
                out_of_corpus_scores.append(maximum_similarity)

        threshold = calibrate_similarity_threshold(out_of_corpus_scores)
        metrics = compute_retrieval_metrics(rankings, k=TOP_K)
        ooc_rate = out_of_corpus_detection_rate(out_of_corpus_scores, threshold)
        answerable_abstentions = sum(score <= threshold for score in answerable_scores)
        p95_latency = float(np.percentile(latencies_ms, 95))
        checks = {
            "recall_at_5": {"value": metrics["recall@5"], "target": 0.8},
            "precision_at_5": {"value": metrics["precision@5"], "target": 0.6},
            "mrr": {"value": metrics["mrr"], "target": 0.7},
            "out_of_corpus_detection": {"value": ooc_rate, "target": 0.9},
            "p95_query_latency_ms": {"value": p95_latency, "target": 800.0},
        }
        checks["p95_query_latency_ms"]["passed"] = p95_latency <= 800.0
        for check_name in ("recall_at_5", "precision_at_5", "mrr", "out_of_corpus_detection"):
            checks[check_name]["passed"] = (
                checks[check_name]["value"] >= checks[check_name]["target"]
            )

        return {
            "version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "dataset": {
                "question_count": len(questions),
                "answerable_count": len(answerable_scores),
                "out_of_corpus_count": len(out_of_corpus_scores),
                "document_ids": [str(document_id) for document_id in sample_ids],
            },
            "metrics": {
                "recall_at_5": metrics["recall@5"],
                "precision_at_5": metrics["precision@5"],
                "mrr": metrics["mrr"],
                "p95_query_latency_ms": p95_latency,
            },
            "calibration": {
                "similarity_threshold": threshold,
                "out_of_corpus_flagged": round(ooc_rate * len(out_of_corpus_scores)),
                "out_of_corpus_total": len(out_of_corpus_scores),
                "answerable_flagged": answerable_abstentions,
                "answerable_total": len(answerable_scores),
                "rule": "flag when the best cosine similarity is less than or equal to the cutoff",
            },
            "acceptance": {
                "checks": checks,
                "passed": all(check["passed"] for check in checks.values()),
            },
            "latency_method": (
                "Warm local embedding model; query embedding plus database retrieval; "
                "excludes process/model cold start."
            ),
        }
    finally:
        provider.close()
        await database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    report = asyncio.run(_run())
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["acceptance"], ensure_ascii=True, indent=2))
    print(f"Full report: {REPORT_PATH}")
    return 0 if report["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
