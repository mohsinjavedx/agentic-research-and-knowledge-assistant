# Phase 8 verification

Date: 23 November 2026. Baseline `e56fb7f`; changes on `phase-8`, uncommitted.
The existing project and database data were preserved.

## Observed checks

- Baseline before implementation: 375 backend tests passed in 154.34 seconds.
- Initial complete updated backend suite: **397 passed in 232.95 seconds**,
  including real PostgreSQL integration tests (`RUN_DB_TESTS=1`).
- Final complete suite after review fixes: **412 passed in 267.89 seconds**;
  no failures or skips locally. Important review findings were reproduced RED,
  then covered by passing regression tests.
- Focused quota/config tests: 29 passed. Focused telemetry/provider/health/CLI
  tests: 51 passed. Parser failures were reproduced before implementation;
  the full run includes the corrected CLI fault-injection fixture.
- Ruff lint and formatting pass; mypy reports no issues in 85 application/migration
  source files. Alembic reports no new schema operations after migration 0006.
- Pinned gitleaks 8.30.1: official SHA-256 verified, synthetic secret detected,
  complete existing Git history (34 commits) has 0 findings.
- Frontend lint, typecheck, Prettier and production webpack build: passed.
- Browser regression: **16 passed**; real Next proxy checks: **2 passed**, including
  >10 MiB PDF forwarding and a 35-second upstream response.
- Final gitleaks history **0**, full `.next` build directory **0** findings using
  the documented narrow Next server-metadata exceptions. Checksum/canaries and
  same-manifest provider injection/client-copy tests passed. The unrestricted
  intermediate scan's 12 framework-key findings are explained in step 2.
- Separate scan of **334 tracked/unignored working files**, including uncommitted
  implementation/docs: **0 findings**. All reports remain redacted.
- Linux smoke after fixes: real text PDF extracted, malformed PDF rejected, no
  staged files/children retained. Ran non-root with networking disabled, read-only
  filesystem and temporary /tmp using the existing parser-check Docker image.
- Live Next→API→Groq `openai/gpt-oss-120b` answer: **200**, correct five benchmark
  names, one citation, no insufficient-evidence/degraded flags. Telemetry recorded
  hashed session, actual usage (4731 mixed local/hosted tokens), safe route and
  request correlation without source text/provider errors.
- Final API readiness and readiness through Next both returned **200 / ready**.
  The API was restarted with proxy headers/access logging disabled. Its final
  background process omits autoreload; the documented development command includes it.

## Fresh review and fix pass

One fresh-context senior review (gpt-6.2-astra) found five Important issues:
native-driver outage handling, active-upload cancellation, root-path quota bypass,
Instructor unknown-usage accounting and optional reranker accounting. All were
reproduced in failing tests, fixed, and included in the final green 412-test suite.
Shallow-history certification was re-graded as Important and guarded too. Negative
Ollama token counts are rejected. Pending build/scan review evidence was resolved
with real runs; regression tests verified the fix pass.

## Acceptance mapping

Persistent quotas are tested with concurrent admissions, clock-window expiry,
new database/app instances, changed cookies and forged forwarding headers.
All three quotas return 429 with Retry-After; outages return a safe 503. Boundary
tests prove rejected bodies do not reach downstream parsing/model work.

Parser tests run real spawned workers on Windows. They kill/join stalled workers,
contain crashes and oversized/malformed IPC, refuse repeated progress, parse a
real PDF and verify temporary cleanup. Existing HTTP upload integration cases
exercise successful indexing, OCR, invalid signature, traversal, MIME and oversize
4xx responses. Secret scanners run against real history/build artifacts; mocked
browser tests do not substitute for those gates.

## Repeat commands

From `apps/api`:

```powershell
$env:RUN_DB_TESTS = '1'
$env:HF_HUB_OFFLINE = '1' # only when model/tokenizer artifacts are already cached
uv run alembic upgrade head
uv run alembic check
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
```

From `apps/web`: `npm run lint`, `npm run typecheck`, `npm run format:check`,
`npm run test:e2e`, `npm run test:proxy`, `npm run build`. Then from root:
`python scripts/scan_secrets.py`.

Full logs/reports are under ignored `tmp/phase8-*` and `tmp/security/`; source
documents, credentials and raw provider errors are not copied into this guide.

## Operational limits

Both IP and session budgets are enforced. Clients behind the same Next proxy/NAT
share the IP allowance. Production needs an explicit trusted-edge policy if it
must distinguish those clients; spoofable forwarding headers stay ignored here.
Changing the identity secret resets identifier-based quotas. Parsing containment
is a process/resource boundary, not a virtual machine; complex valid PDFs may hit
the stricter 15-second document-wide preflight-stage ceiling. Remote CI has not run
until these local changes are pushed. No deployment/history rewrite is performed.

Deferred minor: the supervised adapter currently drops a native page-specific
failure's `page_number` in the CLI error diagnostic. It still returns the safe
failure code. Successfully extracted page mappings, chunk offsets and citations
retain their page numbers. No Phase 8 acceptance gate remains blocked locally.
