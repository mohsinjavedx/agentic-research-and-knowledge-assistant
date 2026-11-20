# Phase 2: Embeddings and unified indexing

| Step | Guide | Status |
| --- | --- | --- |
| 1 | [Embedding providers and model-aware preparation](phase-2-step-1-embedding-providers.md) | Implemented |
| 2 | [Embedding batch metadata and startup compatibility](phase-2-step-2-batch-metadata.md) | Implemented |
| 3 | [Vector and full-text chunk indexes](phase-2-step-3-vector-fts-indexes.md) | Implemented |
| 4 | [Session idempotency and document deletion](phase-2-step-4-session-idempotency-deletion.md) | Implemented |
| 5 | [Expired-session cleanup](phase-2-step-5-expired-session-cleanup.md) | Implemented |

All five Phase 2 steps are documented separately, matching the Phase 1 guide layout. Steps 4–5 add checksum idempotency, anonymous session cookies, owner-scoped deletion, and TTL cleanup.

The local PDF indexing CLI, persistence API, and database lifecycle work for Steps 3–5 are implemented and covered by tests. The session-scoped retrieval route was added in Phase 3 and its PostgreSQL integration test verifies that foreign-session documents are excluded. There is still no public upload route, so browser upload/deduplication is not demonstrated end to end.

See the [evaluation report](../../evaluation-report.md) and [all phase guides](../README.md).
