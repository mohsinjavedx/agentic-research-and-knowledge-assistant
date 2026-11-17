# Phase 2, step 3: Vector and full-text chunk indexes

Implemented: 17–18 November 2026. Status: database vector/FTS structures, atomic persistence, and a local PDF embedding/indexing CLI are implemented. The public upload and retrieval routes are not part of this step.

## What this step delivers in the database

Migration `0003_chunk_indexes` stores one embedding batch and its chunk rows in PostgreSQL:

- Dense vectors use `pgvector vector(384)`.
- Lexical tokens use PostgreSQL `tsvector`.
- Vector retrieval uses an HNSW cosine index.
- Lexical retrieval uses a GIN index.
- Batch and chunk deletion cascades from the document.

The migration creates:

```text
embedding_batches
chunks.embedding
chunks.fts_tokens
ix_chunks_embedding_hnsw
ix_chunks_fts_gin
```

The migration is reversible. Downgrade removes the two indexes and both tables.

## Source files

| File | Purpose |
| --- | --- |
| [0003_chunk_indexes.py](../../../apps/api/migrations/versions/0003_chunk_indexes.py) | Vector and FTS migration, constraints, and indexes. |
| [models.py](../../../apps/api/app/db/models.py) | SQLAlchemy persistence models. |
| [service.py](../../../apps/api/app/services/indexing/service.py) | Validates embedded document identity/provenance/vectors and atomically persists document, batch, and chunks under a PostgreSQL advisory lock. |
| [cli.py](../../../apps/api/app/services/indexing/cli.py) | Validates, extracts, prepares, embeds, optionally exports, and explicitly persists a local PDF. |
| [test_indexing.py](../../../apps/api/tests/integration/test_indexing.py) | Real-database atomic indexing, FTS/vector, rollback, and concurrency coverage. |
| [test_indexing_cli.py](../../../apps/api/tests/unit/test_indexing_cli.py) | CLI help, explicit-scope, overwrite-protection, and malformed-PDF tests. |
| [embeddings.py](../../../apps/api/app/providers/embeddings.py) | Produces validated vectors for persistence. |
| [preparation.py](../../../apps/api/app/services/indexing/preparation.py) | Model-aware chunk preparation. |

## HNSW and GIN indexing

The HNSW index uses cosine distance:

```sql
USING hnsw (embedding vector_cosine_ops)
WITH (m=16, ef_construction=64)
```

The GIN index is built on the generated `fts_tokens` column:

```sql
USING gin (fts_tokens)
```

The generated FTS column uses the English PostgreSQL text search configuration, so both stemming and English query parsing can use `plainto_tsquery('english', ...)`.

## Intended atomic persistence

The Phase 2 plan specifies that a writer must:

1. Prepare model-sized chunks from an already extracted document.
2. Generate vectors outside a database transaction.
3. Acquire a shared advisory lock around model identity validation and batch insertion.
4. Insert the document, one embedding batch, and all chunks in one transaction.
5. Roll back the document, batch, and chunk rows on any database failure.
6. Optionally export JSON without requiring database persistence.

A real persistence service and CLI are implemented. The CLI uses the actual BGE tokenizer and provider, writes vectors only after all inputs pass validation, and performs database work only when `--persist` is explicitly supplied. Local model loading remains lazy until embedding starts.

## Try it with a PDF

From `apps/api`, embed a PDF without persisting it:

```powershell
uv run python -m app.services.indexing.cli 'C:\path\to\paper.pdf'
```

The summary reports the document checksum, page/chunk counts, provider, model, and dimension. To persist it for one anonymous session, ensure PostgreSQL is running and migration `0004_session_lifecycle` is current:

```powershell
uv run alembic upgrade head
$sessionId = [guid]::NewGuid().ToString()
$pdf = 'C:\path\to\paper.pdf'
$first = (uv run python -m app.services.indexing.cli $pdf --persist --session-id $sessionId) | ConvertFrom-Json
$second = (uv run python -m app.services.indexing.cli $pdf --persist --session-id $sessionId) | ConvertFrom-Json
$first.document_id
$second.document_id
```

The IDs should match. The repeat currently performs embedding again, but the idempotent persistence step creates no duplicate rows. Use `--persist --sample` only for global read-only sample documents.

`--output '.\paper-embeddings.json'` writes chunk text, provenance, and vectors to a new JSON file without requiring database persistence. The file may contain private PDF content; choose a protected local path and do not overwrite an existing export.

To delete a session-owned document through the API, start the FastAPI server and send the same session UUID as the cookie:

```powershell
Invoke-WebRequest -Method Delete `
  -Uri "http://127.0.0.1:8000/api/v1/documents/$($first.document_id)" `
  -Headers @{ Cookie = "session_id=$sessionId" }
```

Successful deletion returns `204`; another session receives `404`.

To verify stored batch/chunk counts in PostgreSQL:

```sql
SELECT d.id, d.filename, b.embedding_model, b.embedding_dim, b.chunk_count,
       COUNT(c.id) AS stored_chunks
FROM documents AS d
JOIN embedding_batches AS b ON b.document_id = d.id
LEFT JOIN chunks AS c ON c.batch_id = b.id
WHERE d.id = '<document-id>'
GROUP BY d.id, b.id;
```

## Verification commands

Run the unit/CLI verification:

```powershell
cd apps/api
uv run pytest -q tests/unit/test_embeddings.py tests/unit/test_embedding_compatibility.py tests/unit/test_indexing_cli.py
```

For the real database suite:

```powershell
docker compose up -d --wait db
uv run alembic upgrade head
$env:RUN_DB_TESTS = "1"
uv run pytest -q tests/integration/test_embedding_schema.py tests/integration/test_indexing.py
```

The real integration suite verifies persistence and schema behavior against a migrated, reachable PostgreSQL database. The CLI tests verify that help and validation paths do not load model weights or require database access.

Run general backend quality checks with:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run alembic check
uv run pytest -q
```

## Acceptance status

| PDF acceptance item | Status |
| --- | --- |
| 384-dimensional embedding batch without NaN/Inf | Implemented by provider validation; real 20-chunk smoke exists |
| Batch stores model and dimension metadata | Implemented in migration/models |
| `vector(384)` HNSW index | Migration and schema implemented |
| Generated English `tsvector` GIN index | Migration and schema implemented |
| Atomic document/batch/chunk indexing | Implemented in the internal persistence service |
| 20-chunk numeric integrity | Verified with the real local provider; 27-chunk PDF CLI persistence/idempotency smoke also passed |
| Database persistence | Integration tests verify metadata, FTS/vector queries, rollback, concurrency, and idempotency |

Steps 4–5 add session/checksum idempotency, session-scoped document deletion, and periodic expired-session cleanup. See the [step 4 guide](phase-2-step-4-session-idempotency-deletion.md) and [step 5 guide](phase-2-step-5-expired-session-cleanup.md). A public browser upload and retrieval workflow remains outside this increment.
