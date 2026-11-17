# Phase 2, step 2: Batch metadata and startup compatibility

Implemented: 17 November 2026. Status: database schema and compatibility guard implemented.

## What this step delivers

The second Phase 2 point makes embedding identity persistent and rejects incompatible database/model combinations before the API accepts readiness:

- Every batch records model name, immutable revision, vector dimension, provider, document, and chunk count.
- The vector column is fixed at `vector(384)`.
- The startup compatibility check verifies the actual PostgreSQL column type.
- Persisted batches must use the configured BGE model and pinned revision.
- Ordinary database outages retain liveness and readiness retry behavior.
- A model, revision, or schema mismatch raises a startup compatibility error.

## Source files

| File | Purpose |
| --- | --- |
| [0003_chunk_indexes.py](../../../apps/api/migrations/versions/0003_chunk_indexes.py) | Creates `embedding_batches`, `chunks`, HNSW, and GIN objects. |
| [models.py](../../../apps/api/app/db/models.py) | SQLAlchemy `Document`, `EmbeddingBatch`, and `Chunk` mappings. |
| [embedding_compatibility.py](../../../apps/api/app/db/embedding_compatibility.py) | Checks actual vector dimension and persisted model/revision metadata. |
| [session.py](../../../apps/api/app/db/session.py) | Database readiness integration. |
| [main.py](../../../apps/api/app/main.py) | Startup lifecycle that closes database resources after compatibility failures. |
| [test_embedding_compatibility.py](../../../apps/api/tests/unit/test_embedding_compatibility.py) | Schema/mismatch and startup/outage tests. |
| [test_embedding_schema.py](../../../apps/api/tests/integration/test_embedding_schema.py) | Real PostgreSQL type, index, generated-FTS, and mismatch tests. |

## Persistent batch contract

Each `EmbeddingBatch` belongs to exactly one document and records:

```text
id
document_id
embedding_model
model_revision
embedding_dim
provider
chunk_count
created_at
```

Database constraints require:

- `embedding_dim = 384`
- provider is `local` or `api`
- model and revision are not empty
- chunk count is positive
- one batch per document
- chunk batch/document IDs remain consistent
- document deletion cascades to its batch and chunks

The model identity is pinned to the revision used for local and hosted configuration. This prevents an existing vector index from silently mixing embeddings created by a different model or revision.

## Chunk provenance contract

Each chunk persists:

```text
document_id
batch_id
chunk_index
raw_text
normalized_text
page_start
page_end
char_start
char_end
chunk_metadata
embedding
fts_tokens
```

Chunk constraints preserve the Phase 1 source contract, including ordered offsets, source text length, nonempty normalized text, and single-page provenance.

The PostgreSQL `fts_tokens` column is a persisted generated `tsvector`:

```sql
to_tsvector('english', normalized_text)
```

The generated value follows later updates to `normalized_text` and is not maintained by application-side string copying.

## Startup behavior

On startup, the database compatibility guard checks:

1. The active configured model is the supported BGE model.
2. The actual `chunks.embedding` column is `vector(384)`.
3. Existing batch model and revision values match the active pinned identity.

The guard is lightweight and does not load ONNX weights or call the hosted embedding service. A compatibility mismatch is a configuration/schema error. A normal database connection outage is not promoted to application startup compatibility failure; liveness remains available and readiness can recover after subsequent checks.

## Try it locally

Apply migrations from `apps/api`:

```powershell
uv run alembic upgrade head
uv run alembic check
```

The real-schema integration tests require Docker/PostgreSQL:

```powershell
$env:RUN_DB_TESTS = "1"
uv run pytest -q tests/integration/test_embedding_schema.py tests/integration/test_indexing.py
```

Remove the environment variable in later shells with:

```powershell
Remove-Item Env:RUN_DB_TESTS -ErrorAction SilentlyContinue
```

## Verification

- Unit compatibility tests pass for compatible and mismatched models, vector dimensions, startup failure, and database outage behavior.
- Migration `0003_chunk_indexes` defines:
  - `embedding_batches`
  - `chunks.embedding vector(384)`
  - persisted English `fts_tokens`
  - HNSW cosine index
  - GIN full-text index
- The real PostgreSQL integration suite verifies the actual vector type, generated FTS column, indexes, model mismatch, rollback, and batch metadata behavior.
- Real database verification has to be enabled with `RUN_DB_TESTS=1`; default unit runs may skip it.

This step establishes the storage contract but does not implement upload idempotency or public deletion/cleanup routes.

Next: [step 3, vector and full-text chunk indexes](phase-2-step-3-vector-fts-indexes.md).
