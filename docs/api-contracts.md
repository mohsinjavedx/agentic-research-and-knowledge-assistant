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

Session document persistence is idempotent on `(session_id, checksum)`: a repeat returns the existing document ID without creating a second batch or chunk set. A partial unique database index protects this invariant if concurrent requests race. The current repository does not yet expose a public PDF upload or retrieval route; the internal persistence service accepts a session UUID. Any future retrieval query must restrict results to global samples or the current session.

Expired session documents are deleted by a periodic worker using the strict condition `expires_at < NOW()`. Sample documents are not expired by this worker. OpenAPI is available at `/openapi.json` and `/docs`.
