# Phase 8 security, observability and reliability

Spec: implementation guide v2.0, pages13-14. User authorized starting Phase8;
complete all four steps using the established inline Superpowers/TDD workflow.
Starting point: clean user-created `phase-8` branch at `e56fb7f`. Work in this
checkout and leave changes uncommitted. No history rewriting or publishing.

## Design and acceptance

1. PostgreSQL sliding-window request events:5 chat requests/minute,2 research
   submissions/10 minutes,3 uploads/hour. Record HMAC IP/session identifiers and
   serialize admission with transaction advisory locks. Enforce both dimensions
   so changing a cookie or forwarding header does not create another allowance.
   Return429 with Retry-After, fail closed on database failure, expire old events,
   and prove persistence with a new application/database instance. Search shares
   the chat budget; health, library reads and job polling do not consume it.
2. Run the actual gitleaks scanner against complete Git history and the Next build
   output, with redacted results. Add reproducible commands/CI. Never print secret
   values or rewrite shared history. Any genuine historical finding stays an
   explicit unmet gate requiring remediation rather than an invented clean scan.
3. Keep20MiB/100-page/filename/MIME/signature validation. Move untrusted structure
   checking and native extraction into a disposable spawned process. Parent-owned
   staging, bounded JSON IPC, monotonic progress, a hard15-second page/stage
   deadline and OS memory controls contain crashes/hangs; kill/join on failure.
   Keep embedding models in the parent. All browser/CLI preparation uses the safe
   boundary; native geometric extraction remains the same algorithm.
4. Structured request telemetry: request_id, HMAC session_id, route template,
   latency_ms, actual tokens_used (null when unknown), provider and error_code.
   Carry context into worker threads, record background/provider usage correctly,
   and suppress dependency errors that could echo private content or credentials.

Choose PostgreSQL over process-local counters for restart/multiworker consistency;
choose process termination over thread timeouts because native parsing can remain
running after thread cancellation. Use the existing same-origin frontend and API
contracts. This phase introduces no new UI design or hosted-service requirement.

## Implementation tasks

### 1. Persistent admission control

- [x] RED tests: sliding-window boundaries, simultaneous requests, IP/session
  independence, cookie/header spoofing, new-instance persistence and Retry-After.
- [x] Add `RateLimitEvent`, migration0006, identity hashing, quota service and
  ASGI enforcement before body/model/parser work; retain compatible research guard.
- [x] Apply migration, run real PostgreSQL/API checks, document step1.

### 2. Secret isolation

- [x] Discover/install a pinned official gitleaks release with checksum validation.
- [x] Verify scanner catches synthetic fixtures; scan history and built frontend
  with values redacted. Preserve machine-readable outcomes without raw secrets.
- [x] Add safe repeatable scripts/CI and step2 guide; report genuine blockers.

### 3. Parser containment

- [x] RED tests: hard-kill a stalled parser, bounded/malformed IPC, native crash,
  actual malformed/traversal/oversize/OCR PDFs and temporary cleanup.
- [x] Implement spawned extraction, memory/output bounds, progress deadlines and
  safe error mapping. Reuse normalization/chunking/embedding after extraction.
- [x] Verify real PDFs and malicious cases, then document step3 and platform limits.

### 4. Telemetry and verification

- [x] RED tests: hashed identity, safe route fields, actual/unknown usage,
  thread propagation, background timing and no user text/credential leakage.
- [x] Instrument provider/request paths and dependency logging, document step4.
- [x] Run full tests, lint/format/types, migration check, browser/build checks and
  final secret scans. One fresh read-only senior review, then RED/GREEN fixes.
- [x] Record evidence and every unverified or unmet acceptance item in guides/chat.

## Review focus

- Admission must be atomic across workers and persist across restart, and cannot
  trust arbitrary forwarding headers; shared-IP strictness is a deliberate free-demo
  tradeoff. Start Uvicorn with proxy headers disabled unless trust is configured.
- Hashes must remain stable across restart without storing raw IP/session values.
  Use a dedicated production HMAC secret; development can derive from the existing
  database credential. Rotating that secret intentionally starts new quota keys.
- PDF structure/native code must not execute in the API process, survive timeout,
  send pickle payloads back, or retain temporary files after rejected/cancelled work.
- Telemetry must not invent tokens or log query strings, source text, raw identity,
  SDK exception messages or secrets; synthetic tests must prove those exclusions.
- A clean history/bundle scan must come from a real scanner run, not an allowlist
  that hides genuine findings, and shared Git history must remain intact.

## Progress

Baseline: 375 backend tests passed in 154.34s before changes.

Task 1: quota implementation and migration applied. 29 focused quota/config tests
passed. Identity and rate-limit tests were observed RED before implementation;
cleanup import was also observed RED. Later verification will include the full suite.

Task 2: official gitleaks 8.30.1 installed/checksummed; actual all-history scan found
0 leaks in 34 commits. Repeatable script verified its canary and history gate.
Bundle gate remains pending final frontend build.

Task 3: sandbox tests observed RED (module absent); first implementation passed
77/78 parser/CLI tests. Remaining failure was a stale native monkeypatch across
the new spawn boundary; target the supervised adapter in that CLI unit fixture.

Task 4: telemetry tests observed RED (module absent), implemented and verified.

All four steps implemented; initial full suite 397/397 and checks passed. Frontend
lint/types/format/build, 16 browser tests and 2 real proxy tests passed. Real
Next→API→Groq answer returned all five benchmark names with one citation and no
degraded mode; request telemetry recorded actual mixed hosted/local usage.
Linux non-root/network-disabled real-PDF and malformed-PDF smoke passed with no
staging/children left. Final gitleaks history and build scans both report 0 findings;
334 tracked/unignored working files were separately scanned with 0 findings.

Fresh senior review (gpt-6.2-astra) found five Important issues. Each was reproduced
RED: native DB connection failures, active upload cancellation, root-path bypass,
unknown Instructor usage, missing reranker usage. Fixes passed 37 focused tests;
also rejected negative Ollama counts. Final post-fix suite: 412 passed in 267.89s.
Final lint/format/types (85 source files)/schema checks passed; Linux smoke and
API/Next readiness passed. All local acceptance gates verified.

Final: Ruling: re-grade shallow-history certification as Important — a successful
full-history claim must be true in another checkout too — otherwise leaked older
commits could be missed. Added a RED→GREEN shallow-check guard.
Final: Ruling: narrow server-generated framework metadata exceptions — the raw
bundle scanner found 12 copies of required Next server signing/encryption keys —
whole-file exclusions would hide real credentials. Three field+path+shape AND
exceptions retain all detectors; provider injection in the same file and any
client-side key copy are proven to fail. A mistaken exception could hide a future
framework-shaped server value, so exact paths/shapes and tests must stay narrow.
Final: Ruling: reviewer set pending build/bundle outcomes aside — both now passed
with captured real results — claiming them without fresh evidence would be wrong.
Final: minor (deferred): supervised page-specific parser failures return safe
codes but omit the native error's page_number in the CLI diagnostic. Successful
page mappings/citations are unaffected; no private content is exposed.

Ruling: use independent IP and session budgets — cookie cycling cannot reset a
free-demo quota — users behind the same Next proxy/NAT share the stricter IP limit.
Ruling: keep changes uncommitted on the existing user-created phase-8 branch —
the user did not ask for commits, worktrees, publishing or history rewriting.
Ruling: retain the native adapter injection for algorithm unit tests — spawned
processes do not inherit monkeypatches — production defaults/entry points are
supervised, and separate tests exercise the actual process boundary.
