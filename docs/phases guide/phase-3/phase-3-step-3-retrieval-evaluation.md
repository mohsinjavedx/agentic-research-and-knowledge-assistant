# Phase 3, step 3: Retrieval evaluation

The evaluation runner measures retrieval against the fixed, page-labeled answerable questions in [golden_set.json](../../../data/eval/golden_set.json). It warms the embedding model before timing queries, then records query-embedding plus database-retrieval latency; process startup and cold model load are excluded.

Metrics are calculated on the answerable questions:

- **Recall@5:** fraction of labeled document/page pairs represented in the top five, averaged across questions.
- **Precision@5:** fraction of the top-five returned chunks whose document/page pair is labeled relevant, averaged across questions.
- **MRR:** mean reciprocal rank of the first top-five chunk matching any labeled page.
- **p95 query latency:** 95th percentile of warm query embedding plus database retrieval time.

## Run

From the repository root, with PostgreSQL running, migrations applied, and the sample PDFs indexed:

```powershell
uv run --project apps/api python scripts/run_retrieval_eval.py
```

The script validates that all 40 questions, ground-truth page references, and manifest sample IDs match the indexed corpus. It writes the measured result to `data/eval/retrieval_metrics.json` and exits nonzero if an acceptance target fails.

## Source files

| File | Purpose |
| --- | --- |
| [run_retrieval_eval.py](../../../scripts/run_retrieval_eval.py) | Reproducible query run, metric computation, acceptance checks, and report output. |
| [metrics.py](../../../apps/api/app/services/retrieval/metrics.py) | Page-level ranking metrics and similarity calibration helpers. |
| [evaluation README](../../../data/eval/README.md) | Dataset composition and run instructions. |

