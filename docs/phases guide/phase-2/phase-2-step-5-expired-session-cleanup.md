# Phase 2, step 5: Expired-session cleanup

Implemented: 18 November 2026.

## What this step delivers

The API process runs a background cleanup worker that immediately checks for expired session-owned documents and repeats every 15 minutes. It deletes rows strictly when `expires_at < NOW()`. Global sample documents are excluded.

Deleting the document cascades to its embedding batch and chunks, which removes the stored vectors and generated PostgreSQL FTS tokens with the same database operation.

## Source files

| File | Purpose |
| --- | --- |
| [expired_documents.py](../../../apps/api/app/workers/expired_documents.py) | Expiry deletion query, transactional cleanup operation, and periodic retry loop. |
| [main.py](../../../apps/api/app/main.py) | Starts the worker during application lifespan and cancels/awaits it at shutdown. |
| [locks.py](../../../apps/api/app/db/locks.py) | Shared advisory lock serializes expiry cleanup with idempotent indexing. |
| [models.py](../../../apps/api/app/db/models.py) | Stores the session document expiry and defines cascading ownership relations. |
| [test_document_lifecycle.py](../../../apps/api/tests/integration/test_document_lifecycle.py) | Tests strict expiry cutoff, preservation of live/session-boundary rows, and sample exclusion. |

## Cleanup behavior

The worker's database deletion predicate is equivalent to:

```sql
DELETE FROM documents
WHERE session_id IS NOT NULL
  AND is_sample = false
  AND expires_at < NOW();
```

The query runs in a transaction and obtains the same PostgreSQL advisory lock as indexing. This avoids races with an idempotent re-upload that replaces an already-expired record.

The worker runs once as the API starts, then sleeps for 15 minutes between successful passes. If PostgreSQL reports a SQLAlchemy database error, it emits a sanitized warning and retries after up to 60 seconds. It never logs document text, identifiers, or raw database exception content. Shutdown cancels and awaits the task before disposing the database engine.

Session-owned documents receive an expiry when persisted, based on the configured session TTL. Sample documents do not receive a session expiry and are not deleted by this worker.

## Verification

Apply migrations and run lifecycle integration tests:

```powershell
cd apps/api
uv run alembic upgrade head
$env:RUN_DB_TESTS = "1"
uv run pytest -q tests/integration/test_document_lifecycle.py
```

The cleanup test checks an expired session record is removed, an expiry exactly at the database transaction's `NOW()` boundary is retained, and an expired sample record is untouched.
