# Phase 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task, with failing tests before implementation and one fresh final review.

**Goal:** Deliver the guide's four Advanced RAG steps and verify the exact acceptance criteria.

**Architecture:** Scoped PostgreSQL SQL RRF produces ranked cores; bounded adjacent context preserves each source; an optional lazy ONNX adapter reranks candidates; a reproducible ablation reports quality, latency, and memory independently.

**Tech Stack:** Existing Python3.12/FastAPI/SQLAlchemy/PostgreSQL/pgvector, tokenizers, optional onnxruntime, pytest/Ruff/mypy.

**Spec:** [design.md](design.md).

## Global constraints

- Work in the existing phase-5 branch, preserve earlier artifacts, and leave changes uncommitted.
- RRF k=60. Candidate count20 per branch. Neighbor expansion at most5 extras; same document, adjacent index, high similarity only.
- Reranker default off; model pinned, batch4, pair length512, CPU threads2; no torch/transformers.
- Gain≥0.05 overall Recall@5/MRR or≥0.15 exact-match; recall drop≤0.01; SQL p95≤1200ms; incremental RSS<50MB.
- Never tune golden labels to ranking, count extra context as ranked hits, or call fallback output a reranker result.
- Skip a genuinely blocked stage after documenting it, complete independent work, and list unfinished items in the final response.

## Review focus

- Lexical and neighbor branches must never expose foreign/expired/out-of-scope documents.
- Logical merging must keep original IDs/text/pages and map every quote to an original source range.
- Rank fusion must deduplicate and preserve cosine separately; empty lexical results and stable ties must behave predictably.
- Disabled/failed reranking must not download eagerly, leak data, block all search, or falsely appear applied.
- Benchmark gains and memory/latency claims must use comparable frozen inputs and ranked cores, excluding cold startup honestly.

### Task 1: SQL RRF

Files: `app/services/retrieval/hybrid.py`, `tests/integration/test_retrieval.py`, `tests/unit/test_hybrid_retrieval.py`, step1 guide.

- [x] Preserve a fresh dense baseline; write and observe failing SQL/query-semantics/isolation tests.
- [x] Implement one scoped CTE/window/union/group query with k60 and natural websearch semantics.
- [x] Verify pure/SQL fusion behavior and PostgreSQL scope tests; run a real40-query hybrid check.
- [x] Record measured results and document the SQL structure.

### Task 2: Adjacent context

Files: new `app/services/retrieval/context.py`; retrieval schemas/dataclasses, generation evidence/prompt, search/answer routes; unit/PostgreSQL/API tests; step2 guide.

Interface: `retrieve_context(database, query_vector, query, allowed_doc_ids, settings, *, top_k=5, reranker=None) -> RetrievalResult`; `ContextGroup` identifies anchor/member IDs. `RetrievalResult.ranked` is unchanged top-k; `.evidence` adds bounded original source records.

- [x] Write failing neighbor boundary/score/provenance/group-order/scope tests.
- [x] Implement safe bounded expansion and logical groups, then route them into generation without concatenating identities.
- [x] Expose ranked/context distinction and metadata; verify citation/source ranges remain exact.
- [x] Run unit/API/PostgreSQL checks and a live retrieval/answer smoke; record the outcome.

### Task 3: Optional reranker

Files: new `app/providers/reranking.py`; lifecycle/config/context integration, optional dependency/docs, adapter/pipeline tests; step3 guide.

Interface: `Reranker.rerank(question, candidates) -> list[RetrievedChunk]`, `close()`; factory returns None when disabled. Output adds finite `rerank_score` without changing source identity or cosine.

- [x] Write failing tests for score order/batching/truncation, disabled loading, invalid output, and explicit fallback metadata.
- [x] Implement pinned/checksummed lazy ONNX pair scoring and lifespan ownership.
- [x] Verify real model inference with a controlled relevant/irrelevant pair and resource measurements; if blocked, record and continue.
- [x] Verify integration and safe fallback; retain ENABLE_RERANKER=false by default.

### Task 4: Ablation, gates, and final review

Files: new `scripts/run_phase5_ablation.py`, reproducible result JSON, metric/runner tests, phase5 README and four step guides, API/evaluation/root documentation.

- [x] Write failing gate tests for percentage-point deltas, regressions, missing variants, and evidence-count inflation.
- [x] Implement three-mode40-question ablation with dataset hashes, exact-match slice, warm/cold timings, sampled incremental RSS, and non-overwriting output.
- [x] Run actual ablation; inspect every gate, preserve experiments, and choose the default from measured results.
- [ ] Run full backend/database tests, Ruff lint/format, mypy, live/API smoke, and source/diff checks.
- [ ] Request a fresh final review; fix blocking findings with RED→GREEN verification.
- [ ] Complete per-step guides/ledger and list every unfinished step or unmet acceptance criterion in the final response.
