# Step 1: persistent request limits

POST `/answer` and `/search` share 5 admissions/minute; POST `/research` allows
2/10 minutes; POST `/documents` allows 3/hour. Paths are below `/api/v1`.
GET library, health and research polling remain available while a quota is exhausted.

Migration `0006_rate_limit_events` stores action, timestamp, HMAC IP and HMAC session.
There are no raw IP addresses, session cookies, queries or PDFs in this table.
`consume_quota` locks both identity dimensions in deterministic order, reads the
database clock, and counts the preceding window inside one PostgreSQL transaction.
Admission checks run before request-body reading, extraction, embedding or generation.
Rejected attempts return 429 and a conservative integer `Retry-After` in seconds.
Database outages return 503 with `Retry-After: 5`; they do not grant a free request.
Native driver timeouts/refusals are covered as well as SQLAlchemy errors; the
expiry worker retries the same failure families and preserves task cancellation.
Successful admissions count even when later request validation fails.

Both the IP and session budget must permit admission. Changing the cookie does not
reset an IP allowance, and changing IP does not reset a session allowance. This is
deliberately strict for a free demo: users behind a shared NAT/proxy share an IP
budget. The existing Next proxy makes local browser clients share its backend peer
address. A production trusted-edge/client-IP design is a deployment decision;
arbitrary `X-Forwarded-For` values are never accepted as identity here.
Root-path prefixes are stripped using Starlette's routing semantics, so mounted
or prefixed deployments cannot route around admission checks.

Use the documented Uvicorn command with `--no-proxy-headers` (also set in Docker).
Uvicorn's default loopback proxy trust could otherwise rewrite `scope.client`
before application checks. Do not enable proxy trust without an explicit trusted edge.

Set `PRIVACY_HASH_KEY` to a persistent random value of at least 32 characters in
production. Development derives a domain-separated HMAC key from the existing
database credential when the explicit key is absent. A restart preserves quotas;
rotating the key or development database credential intentionally changes identifiers.
The existing expiry worker removes events older than one hour every 15 minutes.
Keep the legacy research-job guard for already persisted jobs; it also returns
`Retry-After` when it refuses a submission.

From `apps/api`:

```powershell
uv run alembic upgrade head
$env:RUN_DB_TESTS = '1'
uv run pytest tests/integration/test_rate_limits.py tests/unit/test_rate_limit_boundary.py tests/unit/test_private_identity.py -q
```

Observed: the first quota/config verification passed 29 tests. Tests use real
PostgreSQL for simultaneous admission, window expiry, a new Database/application
instance, cookie/header changes, session continuity across IP changes and all three
HTTP quotas. Boundary tests prove no downstream parsing on 429/503. Existing handler
unit fixtures explicitly stub admission because their database objects are mocks;
tests marked `rate_limits` retain real middleware enforcement. No production bypass
or environment-based rate-limit disable flag exists.
