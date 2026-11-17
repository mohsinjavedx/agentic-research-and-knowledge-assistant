# Phase 2, step 1: Embedding providers and model-aware preparation

Implemented: 17 November 2026. Status: provider and preparation implementation complete; hosted live-service verification remains limited to controlled HTTP tests.

## What this step delivers

The first Phase 2 point provides a common embedding interface for local and hosted inference while keeping model identity fixed:

- Model: `BAAI/bge-small-en-v1.5`
- Immutable revision: `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`
- Vector size: 384
- Query instruction: `Represent this sentence for searching relevant passages: `
- Document text: embedded without a query instruction

The provider validates inputs and outputs before callers can persist vectors. Empty text, oversized token counts, zero vectors, NaN, infinity, wrong cardinality, wrong dimensions, malformed hosted responses, and unsupported models are rejected explicitly.

Local inference is lazy. The API process can start and perform health checks without downloading model weights or loading ONNX runtime. Hosted HTTP inference also makes no live request during import or application startup.

## Source files

| File | Purpose |
| --- | --- |
| [embeddings.py](../../../apps/api/app/providers/embeddings.py) | Lazy local ONNX and bounded hosted HTTP providers; 384-dimensional validation and L2 normalization. |
| [identity.py](../../../apps/api/app/providers/identity.py) | Pinned model, revision, dimension, and embedding compatibility exceptions. |
| [config.py](../../../apps/api/app/core/config.py) | Embedding provider, model, batch, timeout, and hosted API settings. |
| [preparation.py](../../../apps/api/app/services/indexing/preparation.py) | Converts Phase 1 chunk settings to BGE-compatible token budgets while preserving source mappings. |
| [splitter.py](../../../apps/api/app/services/chunking/splitter.py) | Optional configurable tokenizer/counting support without changing existing Phase 1 defaults. |
| [test_embeddings.py](../../../apps/api/tests/unit/test_embeddings.py) | Provider, HTTP, normalization, token-budget, and query-prefix tests. |

## Provider contract

```python
class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
    def close(self) -> None: ...
```

Document embeddings and query embeddings use the same model and vector space. A query receives the BGE retrieval prefix, while document chunks do not. The provider batches work at a configurable size and returns a separate 384-value vector for each input.

Local ONNX inference uses CLS pooling and L2-normalized vectors. The provider first validates token counts; it does not silently truncate text.

Hosted responses must use an OpenAI-compatible shape:

```json
{
  "model": "BAAI/bge-small-en-v1.5",
  "data": [
    {"index": 0, "embedding": [0.0]}
  ]
}
```

Rows may arrive in any order, but indexes must cover the batch exactly once. Provider and HTTP failures are converted to stable sanitized errors. API keys, URLs, hosted error bodies, and uploaded text are not exposed in provider exceptions.

## BGE chunk budgets

The BGE model has a 512-token limit including special tokens. Phase 2 preparation reserves two special-token positions and uses a 510-content-token limit.

The Phase 1 600–800 token defaults remain unchanged for the existing ingestion CLI. When embedding preparation is used, the chunker:

1. Reduces the configured maximum to the BGE 510-token content limit.
2. Recalculates the minimum according to the original minimum/maximum ratio.
3. Uses the actual provider tokenizer rather than the offline `cl100k_base` counter.
4. Keeps protected tables and fenced code whole or marks an indivisible block oversized.
5. Raises instead of truncating when a text exceeds the model limit.

Protected oversized blocks remain available in the Phase 1 chunk contract; they must not be silently embedded or cut by the provider.

## Try it locally

```powershell
cd apps/api
uv run python -m pytest -q tests/unit/test_embeddings.py
```

Check the CLI, then embed your own PDF locally (this does not write to PostgreSQL):

```powershell
uv run python -m app.services.indexing.cli --help
uv run python -m app.services.indexing.cli 'C:\path\to\paper.pdf'
```

The first local embedding run may download the pinned BGE tokenizer/model. Install the optional `local-embeddings` dependency group if ONNX Runtime is not available; the full PDF testing and optional persistence instructions are in the [Step 3 guide](phase-2-step-3-vector-fts-indexes.md).

## Verification

- 22 focused embedding/provider tests pass.
- Unit coverage includes CLS pooling, L2 normalization, query prefixes, hosted row reordering, malformed vectors, sanitized HTTP failures, empty inputs, and BGE token limits.
- A real local 20-chunk vector smoke is recorded at [phase2-local-20-chunk-smoke.json](../../../tmp/phase2-local-20-chunk-smoke.json). It reported 20 vectors, 384 dimensions, finite values, and L2-normalized output.
- Hosted inference was tested with `httpx.MockTransport` only. No live hosted API key or service was configured.

This step does not claim public document upload, database persistence, retrieval, or a live hosted-model result.

Next: [step 2, batch metadata and startup compatibility](phase-2-step-2-batch-metadata.md).
