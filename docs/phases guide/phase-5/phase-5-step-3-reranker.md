# Step 3 — Optional CPU reranker

`apps/api/app/providers/reranking.py` implements quantized TinyBERT query/passage scoring. The adapter is lazy and runs on ONNX Runtime CPU. It adds `rerank_score` and reorders candidates while retaining their text, IDs, cosine, and RRF score.

- Model: [`Xenova/ms-marco-TinyBERT-L-2-v2`](https://huggingface.co/Xenova/ms-marco-TinyBERT-L-2-v2).
- Pinned revision: `b76bb5e1fefd66aa36cd108622d768e86c015ff1`.
- Quantized model: 4,496,298 bytes; SHA256 `026c2ec3257cd351696e45bbd6040bb83cf818ba89059b4344bd6350138b62ce`.
- Boundaries: 20 candidates, four pairs per inference batch, 512 tokens per pair, two CPU inference threads, one inter-op thread. Truncation affects only the passage used for scoring, never the stored or returned source text.
- Loading and inference share a lock. The application owns and closes the optional provider during its lifespan.

## Enable locally

From `apps/api`, install the existing ONNX dependency group with `uv sync --group local-embeddings`. Set `ENABLE_RERANKER=true` and restart the API. The first nonempty request downloads the pinned tokenizer and weights into the normal Hugging Face cache. No PyTorch, Transformers, new API credentials, or hosted rerank service is required.

**Default remains `ENABLE_RERANKER=false`**, as required for the 512MB free tier. Disabled mode constructs no reranker and downloads no artifacts. The retrieval mode continues to select the candidate strategy; hybrid+reranker requires both `RETRIEVAL_MODE=hybrid` and the flag.

If loading, inference, or output validation fails, retrieval keeps the original candidate order and reports `reranking_applied=false` plus a stable `reranker_error`. Failures are logged without source text. A benchmark with such a failure is unavailable for adoption, even though retrieval fallback succeeds.

## Verification

Unit tests cover disabled loading, bounded batches, pair truncation, stable ties, unchanged sources, nonfinite/wrong-shaped logits, and fallback metadata. A real pinned-model smoke query, “What is the capital of Germany?”, ranked Berlin above a Washington passage: logits **6.599** versus **−5.954**. Warm two-passage inference was approximately **2.2ms**; first load/inference approximately **9.45s**. This small smoke is not the corpus latency benchmark or a memory claim.

Saved evidence: `data/eval/phase5-reranker-smoke-2026-11-21.json`. Full-corpus ablation and final verification are documented in step 4 and the README.
