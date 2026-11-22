# Phase 5 design: Advanced RAG

Source: implementation guide v2.0, PDF pages 11–12. The user authorized all four steps, per-step verification, and continuing past a blocked stage while reporting every unfinished item. Work stays on the existing clean `phase-5` branch; prior phase changes are committed at `0faa267`.

## Goal and constraints

Improve exact technical retrieval without losing session isolation, citation provenance, or resource bounds. Keep the current Groq generator, pinned BGE embeddings, source corpus, and golden labels unchanged. No frontend, agent workflow, database migration, or additional hosted credentials are required. Leave source changes for the user to commit; do not push or merge.

Acceptance copied from the guide:

- Hybrid RRF improves Recall@5 or MRR by at least **5 percentage points overall**, or **15 points on exact-match/acronym queries**.
- Overall Recall@5 drops by **no more than 1 percentage point** against the Phase 3 baseline.
- Hybrid SQL RRF p95 is **at most 1.2 seconds**, with **less than 50 MB additional RAM overhead**.

The active corrected dataset is used for all three modes. Also retain the published Phase 3 reference. Do not change labels, count expanded neighbors as top-five hits, hide failed variants, or claim unmeasured production/container performance.

## Approaches and decisions

- Move RRF into one scoped SQL query rather than keeping application-side fusion. PostgreSQL ranks vector and `websearch_to_tsquery` lexical candidates independently; combine reciprocal ranks with k=60. Keep cosine, fusion, and neural rerank scores separate. Use natural websearch query semantics rather than rewriting every token into an OR expression; preserve stable ID tie-breaking and empty-lexical fallback.
- Merge adjacent context logically, not by concatenating text under a fabricated single chunk ID. Each original chunk retains its own text, page, and quote ranges. Connected context groups are ordered by chunk index for prompting, and source mappings remain explicit.
- Use a small quantized ONNX TinyBERT cross-encoder rather than the previously slow BGE reranker or another hosted service. The adapter is optional, lazy, and disabled with `ENABLE_RERANKER=false` by default. Reuse the optional ONNX runtime dependency; no torch/transformers dependency is introduced.

## Step 1: SQL RRF

`hybrid.py` performs scoped vector and lexical candidate selection (20 each), ranks with window functions, unions votes, groups by chunk ID, and returns only the final requested rows. Both CTEs apply the same allowed document IDs. The pure fusion helper remains a reference for unit tests; production uses SQL. Tests prove score/order parity, keyword-only recall, query operators, stable ties, and foreign-document exclusion. Failed quality checks leave dense retrieval available.

## Step 2: Adjacent context

Add a context service returning `RetrievalResult(ranked, evidence, context_groups, reranking_applied, reranker_error)`. `ranked` remains the original top-k; `evidence` contains those sources plus at most five distinct adjacent sources. The service fetches only same-document chunk_index±1 candidates, requiring both anchor and neighbor cosine above the calibrated threshold and neighbor similarity within 0.05 of its anchor. These are engineering defaults, not label-tuned settings.

Connected components create logical groups. Each member keeps its UUID, original normalized text, page, and character-range provenance; metadata identifies its group and whether it is additional context. Grouped passages retain their full text and appear together in chunk order in the prompt. The search response separates ranked results from added context; the answer response exposes ranked IDs, groups, and the full evidence pool. Existing citation checks remain in force. Tests cover both boundaries, low-score rejection, duplicates, non-contiguous indices, cross-document/session exclusion, source ranges, and prompt order.

## Step 3: Optional reranker

Use `Xenova/ms-marco-TinyBERT-L-2-v2`, revision `b76bb5e1fefd66aa36cd108622d768e86c015ff1`, with the 4,496,298-byte quantized ONNX file and checksum `026c2ec3257cd351696e45bbd6040bb83cf818ba89059b4344bd6350138b62ce`. Tokenizer and model downloads are pinned; verify the model checksum. Score at most 20 candidates, maximum pair length512, batch size4, CPU threads2, with serialized loading/inference. Truncate only the passage input to the cross-encoder, never the stored evidence returned to the answer service.

The adapter returns original chunk records with a separate finite `rerank_score`. Disabled mode performs no model import/download/load. Optional runtime/download/inference failures return ordinary retrieval with explicit `reranking_applied=false` and a sanitized error code. The benchmark must mark such a neural variant failed/unavailable, never mislabel fallback results as reranked. API lifespan owns adapter cleanup.

## Step 4: Ablation and release decision

Add a non-overwriting runner for Vector-Only, SQL Hybrid RRF, and Hybrid+Reranker on all40 fixed questions. Report dataset/corpus hashes, model revision, per-query ranked IDs, full/exact-match metrics, warm SQL and retrieval/reranking latencies, cold-load cost, and sampled worker RSS. Measure SQL hybrid incremental worker memory after warming embeddings/dense retrieval and before loading the reranker. Report database memory separately if measurable; distinguish worker measurements from deployment/container claims.

Compute acceptance from raw ranked top-five cores; adjacent expansion is verified independently and cannot inflate Recall@5. Record failed variants and unmet gates. Compare with both the active corrected vector baseline and the historical Phase 3 report; the corrected baseline governs the release decision. Only enable hybrid by default if its gain, no-regression, SQL latency, and measured memory checks all pass. Reranker remains disabled on the free-tier default regardless of its exploratory score.

Exact-match membership is frozen in `data/eval/phase5-exact-match-slice.json`: 19 answerable questions selected only from query text mentioning an uppercase acronym, explicit GPT model, OpenBookQA/ScienceQA name, or numbered table. The manifest records the regex, fixed IDs, and active dataset hash. Membership is fixed before hybrid/reranker measurement and cannot be adjusted to obtain a passing alternate gain gate.

Each step has a separate guide, real PostgreSQL checks where needed, lint/format/types, and a progress ledger. One fresh final review covers the integrated code. Per the user's instruction, a blocked model download or quality gate is recorded while independent remaining work proceeds.
