# Foundation security boundaries

Phase 0 exposes only health, liveness, and API documentation. Upload, chat, research tools, anonymous sessions, and quotas are not yet active.

| Boundary | Current protection | Later work |
| --- | --- | --- |
| Configuration | Required typed values; sanitized validation errors; secret fields masked | Provider endpoint configuration and deployment secret store |
| Logs | JSON allowlist; UUID request correlation; no query strings or exception text | Token/cost telemetry and hashed session identifiers |
| Browser/API | Exact CORS origins; no server secrets in browser settings | HttpOnly sessions and ownership checks before upload/retrieval |
| Database | Loopback-only local port; generated ignored development credentials; named volume | Least-privilege hosted runtime role and database-backed quotas |
| Parsing and tools | No parsing or tool execution endpoints | Strict PDF limits, sandboxed parsing, allowlisted read-only tools |

`.env`, model files, uploads, caches, and dependency directories are ignored. The API image uses a non-root user and excludes `.env` and development dependencies. Local generated credentials are for this project's database; the example password is only a development template. No claim of public-demo security or full secret-history audit is made at this phase.
