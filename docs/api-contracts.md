# Phase 0 API contracts

## Readiness

`GET /api/v1/health` returns 200 when database connectivity, pgvector distance operations, and migration `0001_pgvector` succeed:

```json
{
  "status": "ready",
  "db": "connected",
  "pgvector": "<installed version>",
  "embedding_model": "BAAI/bge-small-en-v1.5",
  "llm_provider": "local",
  "model_configured": true
}
```

Failure returns 503 with `status: "not_ready"`, `db: "unavailable"`, and `pgvector: null`. Internal failure details remain private. `model_configured` means settings validation succeeded; Phase 0 does not call an inference provider.

## Liveness

`GET /api/v1/health/live` returns 200 with `{"status":"alive"}` without accessing PostgreSQL.

## Common headers

Readiness requires the latest migration revision, currently `0004_session_lifecycle`. Its first successful database probe also commits ingestion recovery for stale queued/processing documents. Recovery runs once per API process and retries after a startup database failure; subsequent health requests do not repeatedly scan active jobs. The JSON health response shape is unchanged.

Health responses include `Cache-Control: no-store`. API responses carry `X-Request-ID` as a UUID. Valid incoming request UUIDs are reused; invalid values are replaced. Unexpected internal errors return a generic 500 body and the same request ID. CORS uses an explicit origin allowlist and exposes `X-Request-ID` to browsers.

## Anonymous sessions and documents

`POST /api/v1/session` issues a random UUID in an `HttpOnly`, `SameSite=Lax` `session_id` cookie. The cookie has the configured session TTL (24 hours by default) and is marked `Secure` in production.

`DELETE /api/v1/documents/{id}` deletes a session-owned document and cascades to its embedding batch and chunks. The endpoint requires the session cookie. Missing/invalid session cookies return 401; missing, sample, and other-session documents return the same 404 response.

Session document persistence is idempotent on `(session_id, checksum)`: a repeat returns the existing document ID without creating a second batch or chunk set. A partial unique database index protects this invariant if concurrent requests race. The internal persistence service accepts a session UUID; there is not yet a public PDF upload route.

Expired session documents are deleted by a periodic worker using the strict condition `expires_at < NOW()`. Sample documents are not expired by this worker. OpenAPI is available at `/openapi.json` and `/docs`.

## Dense retrieval

`POST /api/v1/search` requires the anonymous `session_id` cookie and a JSON body containing `query`, optional `document_ids`, and optional `top_k` (1–20, default 5). It searches only ready, unexpired documents owned by the current session plus global sample documents. If a caller explicitly requests any missing or other-session document ID, the endpoint returns the same 404 response.

Each result contains a chunk ID, document ID, one-based page number, text, and cosine similarity. The response includes the configured `similarity_threshold` and `insufficient_evidence`, set when no chunks are found or the best similarity is at or below the threshold. This endpoint returns retrieved evidence only; it does not generate or verify an answer.

`RETRIEVAL_MODE` selects `dense` (default) or `hybrid`. Both methods share document visibility. Hybrid combines vector/full-text ranks and adds a separate `fusion_score`; it does not replace cosine similarity. Search returns `retrieval_mode`, and abstention uses the maximum returned cosine regardless of fusion ordering. The corrected comparison does not justify enabling hybrid by default yet.

Phase5 moves hybrid fusion into one scoped PostgreSQL query with `websearch_to_tsquery`, branch candidates20 and RRF k60. Natural phrase/negation operators are preserved. `ENABLE_RERANKER=true` optionally scores20 candidates before selecting top-k; it is false by default. `rerank_score` is a separate neural logit, not a cosine or probability. Responses expose `reranking_applied` and a sanitized `reranker_error`; an optional-provider failure preserves the original retrieval order.

With `ENABLE_CONTEXT_EXPANSION=true` (default), same-document index±1 neighbors can be added if both clear the cosine threshold and the neighbor is within `ADJACENCY_SIMILARITY_MARGIN=0.05` of its anchor. At most `MAX_ADJACENT_CHUNKS=5` extras are returned. Search `results` remains ranked top-k, with extras in `adjacent_context`. `context_groups` contains `anchor_id`, `document_id`, and member `chunk_ids` in source order. Each source retains its original identity/text/page and adds `context_group` and `is_adjacent_context` metadata.

## Grounded answers

`POST /api/v1/answer` requires the same anonymous session cookie and accepts `query`, optional visible `document_ids`, and `top_k` (1–10, default 5). Document visibility is resolved with the same sample/current-session/expiry rules as dense search.

The JSON response contains `answer`, `citations`, `insufficient_evidence`, `degraded_mode`, retrieved `evidence`, and exact `used_evidence` excerpts. Each citation contains a claim, `chunk_id`, `document_id`, one-based `page_number`, source `quote`, and `quote_start`/`quote_end` within the original normalized chunk. Quotes must occur in the actual supplied context and claims must occur in the answer. An invalid-only citation set, uncovered non-whitespace answer characters, or a model insufficiency verdict discards generated prose and abstains. These checks do not establish semantic entailment. Weak retrieval abstains before an LLM call.

Phase5 adds `ranked_chunk_ids`, `context_groups`, `reranking_applied`, and `reranker_error`. `evidence` includes ranked cores plus bounded neighbors. Grouped sources are supplied together in source order with separate evidence indices; each citation still points to exactly one original chunk and range. `used_evidence.retrieval_index` indexes this full pool and can differ from the ordered model `context_index`.

Local and hosted context packing selects whole groups or whole focused standalone passages, skipping units that cannot fit. `HOSTED_LLM_INPUT_TOKEN_BUDGET=6000` bounds the estimated hosted input (messages, schema,25% headroom and64 template tokens). This estimate does not replace the provider's tokenizer, account-wide rate limits, or model context/output constraints. Full retrieval remains visible even when later groups are omitted from model context.

Generation selects focused complete Markdown passages. Local packing fits them within `OLLAMA_NUM_CTX`, reserving `LLM_MAX_OUTPUT_TOKENS` (default 512) and an input margin; oversized passages can be skipped. The full retrieved set remains in `evidence`. Each `used_evidence` item has `context_index`, `retrieval_index`, `start`, and `end`, and its text equals the source slice. Context indices need not equal retrieval indices. Ranges are half-open Unicode-code-point positions, not UTF-16 indices or PDF byte offsets. If no complete passage fits or structured output is incomplete/invalid, the route returns a sanitized HTTP 503.

On an upstream timeout or HTTP 429, the route returns HTTP 200 with `degraded_mode: true`, empty answer citations, and retrieved evidence passages. `insufficient_evidence: false` describes successful retrieval even when generation fails. Other LLM errors return a sanitized HTTP 503. Configure native local Ollama through `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_NUM_CTX`, `LLM_MAX_OUTPUT_TOKENS`, and `LLM_TIMEOUT_SECONDS`; hosted OpenAI-compatible endpoints use `HOSTED_LLM_BASE_URL`, `HOSTED_LLM_MODEL`, and `HOSTED_LLM_API_KEY`. Hosted requests send retrieved text to the configured provider.

## Phase7 browser document library

`GET /api/v1/documents` requires the session cookie and returns up to100 ready
global samples/current-session unexpired documents: `document_id`, `filename`,
`page_count`, `is_sample`, `status`. Foreign/expired documents are excluded.

`POST /api/v1/documents?filename=paper.pdf` requires the session cookie and raw
PDF bytes with `Content-Type: application/pdf` (not multipart). It returns201
with the indexed document summary. Streams are bounded by the configured20MiB
limit and existing100-page/signature/filename checks. Native parsing is serialized
on an app-owned worker; queued cancellation and running/error paths close streams.
Existing scope/checksum idempotence and session TTL apply.

Validation errors return `detail: {code, message}`, including422
`OCR_NOT_SUPPORTED`,413 `FILE_TOO_LARGE`, and415 format/MIME errors. Provider/database
failures return sanitized503 responses. No user-supplied filename becomes a path.

The frontend defaults to same-origin `/api/v1` proxying. `API_INTERNAL_URL` selects
the server-side upstream; credentials are not put in browser environment variables.
Proxy transport permits21MB and190 seconds; API limits and shorter browser
operation deadlines still apply.
