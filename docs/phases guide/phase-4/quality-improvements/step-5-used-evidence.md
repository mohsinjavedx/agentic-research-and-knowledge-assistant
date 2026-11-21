# Step 5: Retrieved and used evidence

The request body is unchanged. `POST /api/v1/answer` now distinguishes:

- `evidence`: the complete retrieved chunks, with their scores and source metadata.
- `used_evidence`: the exact excerpts supplied to a completed generation request, with the same source IDs and scores.

Each used excerpt has `context_index` (the model's zero-based index), `retrieval_index` (its index in `evidence`), and `start`/`end` (the excerpt's half-open Unicode-code-point range within the original normalized chunk). Its `text` must equal that source slice. A context index must not be interpreted directly as an index in the original retrieval array.

The service rejects provider mappings that do not match the original retrieved source and range. This keeps citations correct when packing skips an oversized passage or uses a different subset.

A completed generation that abstains can still expose its supplied excerpts for inspection. Weak-evidence abstention before generation has no used context. Timeout/429 fallback has an empty `used_evidence` list because no completed generation context is returned; it is not a claim that no text was sent upstream.

Inspect `/docs` for the full response schema. Existing clients can continue reading `evidence` and the original citation fields; the new quote and context fields are additive to the HTTP response. Internal Python provider adapters now return `GenerationResult(response, passages)` instead of a bare draft.
