# Phase 5 — Advanced RAG

All four implementation steps are present. **Phase acceptance is not yet passed:** the measured hybrid quality gain is below the guide's target. Dense remains the default and reranking remains disabled. No golden labels, embedding model, or Groq settings were changed.

## Step guides

1. [SQL reciprocal rank fusion](phase-5-step-1-sql-rrf.md)
2. [Adjacent context with original source IDs](phase-5-step-2-adjacent-context.md)
3. [Optional quantized CPU reranker](phase-5-step-3-reranker.md)
4. [Three-mode ablation and acceptance](phase-5-step-4-ablation.md)

[Design](design.md), [implementation plan](implementation-plan.md), and [progress record](progress.md) explain decisions and verification.

## Working flow and source structure

`/search` and `/answer` check session visibility, embed the question, and call `services/retrieval/context.py`. This delegates ranked retrieval to `search.py`: `dense.py` supplies vector-only candidates, while `hybrid.py` ranks vector and full-text branches in one PostgreSQL CTE query with RRF k=60. An enabled reranker reorders up to20 candidates before selecting top-k. Adjacent expansion then adds up to5 original source records. Generation groups related records in document order and verifies citations against the original chunk text.

- `app/services/retrieval/context.py`: distinct ranked/evidence pools, safe neighbor lookup and grouping, optional reranker integration.
- `app/services/retrieval/hybrid.py`: scoped SQL candidate ranking and fusion; no migration is needed because vector/FTS indexes already exist.
- `app/providers/reranking.py`: pinned/checksummed, lazy TinyBERT ONNX adapter.
- `app/schemas/retrieval.py`, `app/schemas/answers.py`: additive context, ranking, and fallback metadata.
- `app/services/generation/{evidence,prompt,answer}.py`: full grouped sources, prompt boundaries, and preserved public source metadata.
- `app/services/generation/context.py`: shared whole-group context budgeting; hosted input estimate defaults to6000 tokens through `HOSTED_LLM_INPUT_TOKEN_BUDGET`.
- `scripts/run_phase5_ablation.py`: non-overwriting, frozen-input comparison and acceptance calculations.
- `data/eval/phase5-*.json`: baseline, neural smoke, full ablation, and retained unsuccessful lexical experiments.
- New PostgreSQL, prompt, adapter, API, and metric tests exercise the integration.

## Reproduce

From the repository root, with PostgreSQL running and samples indexed:

```powershell
uv run --project apps/api python scripts/run_phase5_ablation.py
```

Each run creates a new timestamped report and exits nonzero when hybrid acceptance is not met. The neural variant needs the existing `local-embeddings` ONNX dependency group. No hosted generation request is made by the ablation.

From `apps/api`:

```powershell
$env:RUN_DB_TESTS = "1"
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

API behavior is selectable through `.env`: `RETRIEVAL_MODE=dense|hybrid`, `ENABLE_CONTEXT_EXPANSION=true|false`, `ADJACENCY_SIMILARITY_MARGIN=0.05`, `MAX_ADJACENT_CHUNKS=5`, and `ENABLE_RERANKER=false|true`. Restart after changing environment settings. Keep reranking off on the free-tier default.

## Measured results and unfinished acceptance

On the same40 questions and unchanged corpus, corrected vector baseline Recall@5 is **76.67%** and MRR **0.6244**. SQL Hybrid Recall@5 is **76.67%**, MRR **0.6078**; its SQL roundtrip p95 is **17.64ms**, with approximately **1.95MB additional benchmark-worker RSS**. Hybrid+TinyBERT Recall@5 is **78.33%**, MRR **0.5694**, with about **72.38MB additional worker RSS**. These are development-machine measurements, not a held-out evaluation or cloud deployment test.

The required gain of ≥5 percentage points overall or ≥15 on the frozen exact-match slice is **unmet**. Hybrid recall non-regression and measured worker latency/memory checks pass. Whole deployment/database/container memory remains unmeasured; worker RSS does not establish that broader budget. The optional reranker also exceeds50MB in this measurement and is not promoted.

Full report: [natural-query ablation](../../../data/eval/phase5-ablation-natural-2026-11-21.json). See step4 for the historical baseline, failed experiments, and measurement limits. Final software checks and API smoke evidence are recorded in the progress record.

The real Groq answer smoke returned the correct five benchmarks and one verified source citation after adding the bounded hosted context. An initial413 failure is preserved separately, along with the successful repeat in `data/eval/phase5-api-smoke-budgeted-2026-11-21.json`. This focused smoke does not establish full Phase4 generation acceptance.
