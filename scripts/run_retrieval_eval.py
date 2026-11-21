"""Run the Phase 3 dense-retrieval baseline and calibrate its abstention cutoff."""

import argparse
import asyncio
import hashlib
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
from app.services.retrieval.metrics import (  # noqa: E402
    calibrate_similarity_threshold,
    compute_retrieval_metrics,
    out_of_corpus_detection_rate,
)
from app.services.retrieval.search import RetrievalMode, search_evidence  # noqa: E402

GOLDEN_SET_PATH = REPOSITORY_ROOT / "data" / "eval" / "golden_set.json"
SAMPLE_MANIFEST_PATH = REPOSITORY_ROOT / "data" / "samples" / "manifest.json"
REPORT_PATH = REPOSITORY_ROOT / "data" / "eval" / "retrieval_metrics.json"
TOP_K = 5


def _read_inputs(
    golden_set_path: Path = GOLDEN_SET_PATH,
) -> tuple[list[dict[str, Any]], list[UUID]]:
    golden_set = json.loads(golden_set_path.read_text(encoding="utf-8"))
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


def _dataset_metadata(path: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(content).hexdigest(),
        "revision": json.loads(content).get("revision", 1),
    }


async def _run(
    golden_set_path: Path = GOLDEN_SET_PATH, mode: RetrievalMode = "dense"
) -> dict[str, Any]:
    questions, sample_ids = _read_inputs(golden_set_path)
    dataset_metadata = await asyncio.to_thread(_dataset_metadata, golden_set_path)
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
        query_results: list[dict[str, Any]] = []
        for item in questions:
            started = perf_counter()
            results = await search_evidence(
                database,
                provider,
                item["question"],
                sample_ids,
                top_k=TOP_K,
                mode=mode,
            )
            latencies_ms.append((perf_counter() - started) * 1000)
            maximum_similarity = max((item.cosine_similarity for item in results), default=-1.0)
            query_results.append(
                {
                    "id": item["id"],
                    "question": item["question"],
                    "answerable": item["answerable"],
                    "ground_truth": item["ground_truth"],
                    "latency_ms": latencies_ms[-1],
                    "max_cosine_similarity": maximum_similarity,
                    "results": [
                        {
                            "chunk_id": str(result.chunk_id),
                            "document_id": str(result.document_id),
                            "page_number": result.page_number,
                            "cosine_similarity": result.cosine_similarity,
                            "fusion_score": result.fusion_score,
                        }
                        for result in results
                    ],
                }
            )
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
                **dataset_metadata,
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
            "retrieval_mode": mode,
            "queries": query_results,
        }
    finally:
        provider.close()
        await database.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=GOLDEN_SET_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mode", choices=["dense", "hybrid"], default="dense")
    args = parser.parse_args(argv)
    output = args.output or REPORT_PATH.with_name(
        f"retrieval-{args.mode}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    )
    if output.exists():
        parser.error(f"Refusing to overwrite existing report: {output}")
    if not args.dataset.is_file():
        parser.error("The dataset path must identify an existing JSON file.")
    report = asyncio.run(_run(args.dataset, args.mode))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=True, indent=2) + "\n")
    print(json.dumps(report["acceptance"], ensure_ascii=True, indent=2))
    print(f"Full report: {output}")
    return 0 if report["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
