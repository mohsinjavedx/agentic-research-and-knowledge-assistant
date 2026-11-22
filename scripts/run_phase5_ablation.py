"""Compare ranked top-five retrieval on frozen inputs; never overwrite a report."""

import argparse
import asyncio
import gc
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from time import perf_counter
from typing import Any

import numpy as np
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps/api"))

from scripts.run_retrieval_eval import GOLDEN_SET_PATH, _read_inputs  # noqa: E402

from app.core.config import load_settings  # noqa: E402
from app.db.models import Chunk, Document  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.providers.embeddings import create_embedding_provider  # noqa: E402
from app.providers.reranking import (  # noqa: E402
    RERANKER_MODEL,
    RERANKER_REVISION,
    RERANKER_SHA256,
    RerankerError,
    TinyBERTReranker,
)
from app.services.retrieval.metrics import compute_retrieval_metrics  # noqa: E402
from app.services.retrieval.search import retrieve_evidence  # noqa: E402

SLICE_PATH = ROOT / "data/eval/phase5-exact-match-slice.json"


def summarize(queries: list[dict[str, Any]], ids: set[str] | None = None) -> dict[str, float]:
    return compute_retrieval_metrics(
        [
            (
                [(row["document_id"], row["page_number"]) for row in query["results"][:5]],
                {(row["document_id"], row["page_number"]) for row in query["ground_truth"]},
            )
            for query in queries
            if query["answerable"] and (ids is None or query["id"] in ids)
        ]
    )


def check_gates(baseline: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    overall = {
        metric: variant["metrics"][metric] - baseline["metrics"][metric]
        for metric in ("recall@5", "mrr")
    }
    exact = {
        metric: variant["exact_match_metrics"][metric] - baseline["exact_match_metrics"][metric]
        for metric in ("recall@5", "mrr")
    }
    sql, memory = variant.get("sql_p95_ms"), variant.get("incremental_worker_rss_bytes")
    checks = {
        "measured_variant": variant.get("available") is True,
        "quality_gain": max(overall.values()) >= 0.05 - 1e-12
        or max(exact.values()) >= 0.15 - 1e-12,
        "recall_non_regression": overall["recall@5"] >= -0.01 - 1e-12,
        "sql_p95": sql is not None and sql <= 1200,
        "incremental_worker_rss": memory is not None and memory < 50_000_000,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "overall_delta_percentage_points": {k: v * 100 for k, v in overall.items()},
        "exact_match_delta_percentage_points": {k: v * 100 for k, v in exact.items()},
    }


def worker_rss_bytes() -> int:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                *[
                    (name, ctypes.c_size_t)
                    for name in (
                        "PeakWorkingSetSize",
                        "WorkingSetSize",
                        "QuotaPeakPagedPoolUsage",
                        "QuotaPagedPoolUsage",
                        "QuotaPeakNonPagedPoolUsage",
                        "QuotaNonPagedPoolUsage",
                        "PagefileUsage",
                        "PeakPagefileUsage",
                    )
                ],
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        if not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise OSError("Cannot read process working set")
        return int(counters.WorkingSetSize)
    resident_pages = int(Path("/proc/self/statm").read_text().split()[1])
    return resident_pages * os.sysconf("SC_PAGE_SIZE")


class MemorySample:
    """Sample current working set at 5ms, including cold reranker allocation."""

    def __init__(self) -> None:
        gc.collect()
        self.baseline = worker_rss_bytes()
        self.peak = self.baseline
        self.error: str | None = None
        self._stop = Event()
        self._thread = Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self._stop.is_set():
            try:
                self.peak = max(self.peak, worker_rss_bytes())
            except OSError:
                self.error = "RSS_SAMPLING_FAILED"
                return
            self._stop.wait(0.005)

    def start(self) -> None:
        self._thread.start()

    def finish(self) -> dict[str, Any]:
        self._stop.set()
        self._thread.join()
        self.peak = max(self.peak, worker_rss_bytes())
        return {
            "baseline_worker_rss_bytes": self.baseline,
            "peak_worker_rss_bytes": self.peak,
            "incremental_worker_rss_bytes": None if self.error else self.peak - self.baseline,
            "rss_error": self.error,
        }


async def corpus_digest(database: Database, document_ids: list[Any]) -> dict[str, Any]:
    digest = hashlib.sha256()
    async with database.sessions() as session:
        ready = set(
            (
                await session.scalars(
                    select(Document.id).where(
                        Document.id.in_(document_ids),
                        Document.is_sample.is_(True),
                        Document.status == "ready",
                    )
                )
            ).all()
        )
        if ready != set(document_ids):
            raise RuntimeError("Index the complete sample corpus before running the ablation.")
        rows = (
            (
                await session.execute(
                    select(Chunk)
                    .where(Chunk.document_id.in_(document_ids))
                    .order_by(Chunk.document_id, Chunk.chunk_index)
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            digest.update(
                json.dumps(
                    [
                        str(row.id),
                        str(row.document_id),
                        row.chunk_index,
                        row.page_start,
                        row.page_end,
                        row.normalized_text,
                    ],
                    ensure_ascii=True,
                ).encode()
            )
            digest.update(np.asarray(row.embedding, dtype="<f4").tobytes())
    return {
        "sha256": digest.hexdigest(),
        "chunk_count": len(rows),
        "hash_scope": "ordered IDs, index, pages, normalized text, little-endian float32 vectors",
    }


async def run_ablation(dataset: Path) -> dict[str, Any]:
    questions, document_ids = await asyncio.to_thread(_read_inputs, dataset)
    dataset_bytes = await asyncio.to_thread(dataset.read_bytes)
    dataset_sha = hashlib.sha256(dataset_bytes).hexdigest()
    exact_slice = json.loads(await asyncio.to_thread(SLICE_PATH.read_text, encoding="utf-8"))
    if exact_slice["dataset_sha256"] != dataset_sha:
        raise ValueError("The frozen exact-match slice belongs to a different dataset.")
    exact_ids = set(exact_slice["question_ids"])
    if not exact_ids or not exact_ids <= {q["id"] for q in questions if q["answerable"]}:
        raise ValueError("Invalid exact-match slice IDs.")
    settings = load_settings()
    database = Database(settings)
    embeddings = create_embedding_provider(settings)
    reranker = TinyBERTReranker()
    try:
        await database.check()
        corpus = await corpus_digest(database, document_ids)
        embedding_times, vectors = [], []
        for question in questions:
            started = perf_counter()
            vectors.append(await asyncio.to_thread(embeddings.embed_query, question["question"]))
            embedding_times.append((perf_counter() - started) * 1000)
        # Warm the connection, SQL caches, and dense ORM paths before measuring extra RAM.
        await retrieve_evidence(database, vectors[0], questions[0]["question"], document_ids)
        variants = {}
        for name, mode, neural in (
            ("vector_only", "dense", False),
            ("hybrid_rrf", "hybrid", False),
            ("hybrid_reranker", "hybrid", True),
        ):
            sampler = MemorySample()
            sampler.start()
            cold_reranker_ms, failure = None, None
            sql_times, rerank_times, queries = [], [], []
            try:
                warm = await retrieve_evidence(
                    database,
                    vectors[0],
                    questions[0]["question"],
                    document_ids,
                    mode=mode,
                    top_k=20 if neural else 5,
                )
                if neural:
                    started = perf_counter()
                    try:
                        await asyncio.to_thread(reranker.rerank, questions[0]["question"], warm)
                    except RerankerError as exc:
                        failure = exc.error_code
                    cold_reranker_ms = (perf_counter() - started) * 1000
                for item, vector in zip(questions, vectors, strict=True):
                    started = perf_counter()
                    results = await retrieve_evidence(
                        database,
                        vector,
                        item["question"],
                        document_ids,
                        mode=mode,
                        top_k=20 if neural else 5,
                    )
                    sql_times.append((perf_counter() - started) * 1000)
                    started = perf_counter()
                    applied = False
                    if neural and failure is None:
                        try:
                            results = await asyncio.to_thread(
                                reranker.rerank, item["question"], results
                            )
                            applied = True
                        except RerankerError as exc:
                            failure = exc.error_code
                    rerank_times.append((perf_counter() - started) * 1000 if neural else 0.0)
                    queries.append(
                        {
                            "id": item["id"],
                            "question": item["question"],
                            "answerable": item["answerable"],
                            "ground_truth": item["ground_truth"],
                            "sql_ms": sql_times[-1],
                            "rerank_ms": rerank_times[-1],
                            "reranking_applied": applied,
                            "results": [
                                {
                                    "chunk_id": str(row.chunk_id),
                                    "document_id": str(row.document_id),
                                    "page_number": row.page_number,
                                    "cosine_similarity": row.cosine_similarity,
                                    "fusion_score": row.fusion_score,
                                    "rerank_score": row.rerank_score,
                                }
                                for row in results[:5]
                            ],
                        }
                    )
            finally:
                memory = sampler.finish()
            combined = np.asarray(sql_times) + np.asarray(rerank_times)
            variants[name] = {
                "available": failure is None,
                "error": failure,
                "metrics": summarize(queries),
                "exact_match_metrics": summarize(queries, exact_ids),
                "sql_p95_ms": float(np.percentile(sql_times, 95)),
                "rerank_p95_ms": float(np.percentile(rerank_times, 95)),
                "retrieval_p95_ms": float(np.percentile(combined, 95)),
                "cold_reranker_ms": cold_reranker_ms,
                **memory,
                "queries": queries,
            }
        if corpus != await corpus_digest(database, document_ids):
            raise RuntimeError("The indexed corpus changed during the ablation.")
        if dataset_sha != hashlib.sha256(await asyncio.to_thread(dataset.read_bytes)).hexdigest():
            raise RuntimeError("The golden dataset changed during the ablation.")
        baseline = variants["vector_only"]
        return {
            "version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "dataset": {
                "sha256": dataset_sha,
                "revision": json.loads(dataset_bytes).get("revision", 1),
                "question_count": len(questions),
            },
            "corpus": corpus,
            "exact_match_slice": exact_slice,
            "reranker": {
                "model": RERANKER_MODEL,
                "revision": RERANKER_REVISION,
                "onnx_sha256": RERANKER_SHA256,
            },
            "method": {
                "top_k": 5,
                "candidates_per_branch": 20,
                "rrf_k": 60,
                "adjacent_context": "excluded from ranking metrics",
                "sql_timing": "client-observed SQL roundtrip plus ORM hydration; no embedding",
                "memory_scope": (
                    "benchmark worker RSS only; database/server/container RAM unmeasured"
                ),
                "memory_baseline": "warm BGE and dense SQL, before cold reranker load",
                "memory_sampling_ms": 5,
                "units": "decimal bytes; gains in percentage points",
            },
            "embedding_ms": embedding_times,
            "variants": variants,
            "acceptance": {
                name: check_gates(baseline, variants[name])
                for name in ("hybrid_rrf", "hybrid_reranker")
            },
            "ablation_complete": all(variant["available"] for variant in variants.values()),
        }
    finally:
        embeddings.close()
        reranker.close()
        await database.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=GOLDEN_SET_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or ROOT / "data/eval" / (
        f"phase5-ablation-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    )
    if output.exists():
        parser.error(f"Refusing to overwrite existing report: {output}")
    if not args.dataset.is_file():
        parser.error("The dataset path must identify an existing JSON file.")
    report = asyncio.run(run_ablation(args.dataset))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["acceptance"], indent=2))
    print(f"Full report: {output}")
    return 0 if report["ablation_complete"] and report["acceptance"]["hybrid_rrf"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
