# Phase 2, step 4: Session idempotency and document deletion

Implemented: 18 November 2026.

## What this step delivers

Session-owned documents are now idempotent on `(session_id, checksum)`. Re-persisting the same PDF for the same anonymous session returns the existing document ID and leaves its embedding batch and chunks untouched. A different session can independently index the same checksum.

The API now provides:

- `POST /api/v1/session` to issue a random 24-hour session cookie.
- `DELETE /api/v1/documents/{id}` to remove a document owned by that session.

The delete endpoint intentionally treats an unknown ID, another session's document, and a global sample document the same way: `404 Document not found`. This avoids revealing whether a document belonging to another session exists. Missing or malformed session cookies receive `401`.

## Source files

| File | Purpose |
| --- | --- |
| [service.py](../../../apps/api/app/services/indexing/service.py) | Checks for a matching session/checksum under the indexing advisory lock and returns the canonical document ID without inserting duplicate rows. |
| [models.py](../../../apps/api/app/db/models.py) | Declares the partial unique session/checksum index in ORM metadata. |
| [0004_session_lifecycle.py](../../../apps/api/migrations/versions/0004_session_lifecycle.py) | Adds the database-enforced partial unique index. |
| [sessions.py](../../../apps/api/app/api/v1/sessions.py) | Creates an HttpOnly, SameSite=Lax UUID session cookie and validates it for routes. |
| [documents.py](../../../apps/api/app/api/v1/documents.py) | Implements owner-scoped cascading deletion. |
| [test_indexing.py](../../../apps/api/tests/integration/test_indexing.py) | Tests same-session deduplication and cross-session separation. |
| [test_document_lifecycle.py](../../../apps/api/tests/integration/test_document_lifecycle.py) | Tests missing/foreign session rejection and cascade deletion. |

## Idempotent persistence

Before creating database rows, `persist_document()` acquires the shared transaction-scoped PostgreSQL advisory lock and checks for a non-expired session document with the same checksum. If it finds one, it returns that existing `document_id`.

The partial unique index on `(session_id, checksum)` for non-sample session documents provides a database-level race guard. The service lock serializes normal indexing writers; the index prevents duplicate rows if another writer bypasses that code path.

Expired matching rows are removed during a re-index attempt so an expired document is not returned as current. Its batch and chunks are removed by foreign-key cascade.

Sample documents are not session-keyed and are outside this idempotency rule.

## Session cookie and deletion

Call the session endpoint before session-owned API operations:

```http
POST /api/v1/session
```

The response body is empty. The browser receives a random UUID in an `HttpOnly`, `SameSite=Lax` cookie named `session_id`, scoped to `/api/v1`. The cookie age follows `SESSION_TTL_HOURS` (24 hours by default) and is marked `Secure` in production.

Deletion uses the cookie as the owner credential:

```http
DELETE /api/v1/documents/7d394d37-a4d2-48f0-b993-09bc9f8b0391
Cookie: session_id=<browser-managed>
```

A successful request returns `204 No Content`. PostgreSQL cascades the delete from the document to its embedding batch and chunks, including the vector and generated FTS data. This route cannot delete global sample documents.

## Current boundary

The local PDF indexing CLI can persist a PDF with a `session_id`, but the repository still has no public PDF upload route. The session and delete endpoints can be exercised, and CLI persistence can verify same-session idempotency, while a complete browser upload-and-deduplicate workflow awaits the upload endpoint. Session-scoped retrieval was added in Phase 3; its integration test confirms a session cannot retrieve another session's document and can retrieve global samples plus its own documents.

## Verification

Run the real PostgreSQL lifecycle tests after migrating:

```powershell
cd apps/api
uv run alembic upgrade head
$env:RUN_DB_TESTS = "1"
uv run pytest -q tests/integration/test_indexing.py tests/integration/test_document_lifecycle.py
```

The tests verify that same-session checksum repeats return one document and create no duplicate batch/chunks, the same checksum in another session is independent, an owner can delete its document, a missing or foreign cookie cannot, and a successful delete removes every dependent database row.
