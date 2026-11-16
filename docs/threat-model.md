# Foundation security boundaries

Phase 0 exposes only health, liveness, and API documentation. Upload, chat, research tools, anonymous sessions, and quotas are not yet active.

Phase 1 step 1 adds an internal PDF validator and local CLI. It enforces filename, extension, MIME declaration, signature, actual byte and page limits, and structural/encryption checks. UUID-named temporary copies are removed on context exit. This increment does not expose an upload endpoint or introduce parser isolation; extraction and its execution controls are later work.

Phase 1 step 2 adds synchronous, local Markdown extraction. It uses geometric layout analysis, does not invoke OCR or export images, sanitizes extraction failures, and keeps native parser handles away from the temporary PDF path. Explicit CLI exports contain document text and are intended for local inspection. Parser isolation, hard execution timeouts, and public upload access controls remain future work.

Step 3 checks readable native text before layout processing and rejects predominantly text-poor PDFs with `OCR_NOT_SUPPORTED`. Its strict ratio check allows early abort using the known total page count. Error diagnostics contain only page numbers, thresholds, and counts. This heuristic does not replace parser isolation, execution limits, or a representative-corpus quality assessment.

Steps 4-6 retain original source Markdown while indexing a separate normalized representation, verify chunk source spans, and count tokens without runtime vocabulary downloads. New document rows require either sample visibility or a session UUID, but cookie/ownership-filtered public APIs are still pending. Startup recovery only updates stale active statuses; terminal and fresh rows are preserved, with count-only telemetry. Local preparation exports are explicit and do not persist document text/chunks in PostgreSQL yet.

| Boundary | Current protection | Later work |
| --- | --- | --- |
| Configuration | Required typed values; sanitized validation errors; secret fields masked | Provider endpoint configuration and deployment secret store |
| Logs | JSON allowlist; UUID request correlation; no query strings or exception text | Token/cost telemetry and hashed session identifiers |
| Browser/API | Exact CORS origins; no server secrets in browser settings | HttpOnly sessions and ownership checks before upload/retrieval |
| Database | Loopback-only local port; generated ignored development credentials; named volume | Least-privilege hosted runtime role and database-backed quotas |
| Parsing and tools | Internal validation, text-density rejection, and geometric Markdown extraction with bounded input and temporary-file cleanup; no parsing or tool execution endpoints | Parser isolation, execution limits, allowlisted read-only tools |

`.env`, model files, uploads, caches, and dependency directories are ignored. The API image uses a non-root user and excludes `.env` and development dependencies. Local generated credentials are for this project's database; the example password is only a development template. No claim of public-demo security or full secret-history audit is made at this phase.
