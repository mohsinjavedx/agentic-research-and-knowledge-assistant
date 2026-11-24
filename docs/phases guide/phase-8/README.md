# Phase 8: security, observability and reliability

Implementation guide v2.0, pages 13–14. This phase adds the four operational
safeguards around the existing retrieval/research/UI flows:

1. [Persistent rate limits](01-persistent-rate-limits.md): PostgreSQL sliding
   windows, HMAC identities, atomic admission, 429/Retry-After across restarts.
2. [Secret isolation](02-secret-isolation.md): checksum-pinned gitleaks, full
   history and production bundle scans, redaction and a synthetic detector check.
3. [PDF parser containment](03-pdf-parser-containment.md): spawned native workers,
   15-second deadlines, memory/output bounds, safe errors and temporary cleanup.
4. [Private telemetry](04-private-telemetry.md): request correlation, hashed
   sessions, actual/unknown token counts, provider and classified error fields.

See [design and plan](design-and-plan.md) for decisions, and
[verification](verification.md) for acceptance evidence and outstanding checks.
Changes remain on the existing `phase-8` branch for review.

Apply migration 0006 before running the updated API:

```powershell
cd apps/api
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

Production requires a persistent random `PRIVACY_HASH_KEY` of at least 32
characters. Local development can use the existing database credential derivation.
Do not put this value or provider keys in frontend environment variables.
