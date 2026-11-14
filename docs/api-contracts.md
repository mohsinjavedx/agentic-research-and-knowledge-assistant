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

Health responses include `Cache-Control: no-store`. API responses carry `X-Request-ID` as a UUID. Valid incoming request UUIDs are reused; invalid values are replaced. Unexpected internal errors return a generic 500 body and the same request ID. CORS uses an explicit origin allowlist and exposes `X-Request-ID` to browsers.

Document, chat, and research endpoints are planned in the supplied guide but intentionally not exposed until their phases implement the promised behavior. OpenAPI is available at `/openapi.json` and `/docs`.
