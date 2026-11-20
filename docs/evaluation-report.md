# Phase 0 acceptance report

Verification date: 14 November 2026. Scope: local project foundation only.

| Gate | Evidence | Result |
| --- | --- | --- |
| API readiness | Real PostgreSQL 16 with pgvector; vector operator and Alembic revision verified; 10/10 integration requests and 10/10 actual HTTP requests returned 200 | Pass |
| Configuration guard | Isolated source tree without `.env`; actual app import fails for missing required settings and invalid database URL; credential sentinel absent from output | Pass |
| Backend lint and format | Ruff check and format check | Pass |
| Backend types | Mypy strict mode, 14 source files | Pass |
| Backend smoke and integration | 20 tests passed with `RUN_DB_TESTS=1` against real PostgreSQL | Pass |
| Clean backend source | Isolated copy without `.env`: 18 tests passed; 2 database integration tests correctly skipped | Pass |
| Migration state | `alembic upgrade head`, revision `0001_pgvector`; `alembic check` reports no pending operations | Pass |
| Frontend lint and types | ESLint; Next route type generation followed by TypeScript | Pass |
| Frontend production build | Next.js 16.4.6 / React 19.3.1, Webpack with one worker | Pass |
| Frontend HTTP smoke | `/`, `/workspace`, `/documents`, `/research/smoke` all return 200 from the production server | Pass |
| Browser/API boundary | Real HTTP request with allowed browser origin returns exact CORS origin and request ID | Pass |
| Database recovery | Local container stopped during setup; restart retained pgvector and migration revision; API recovered without restarting its process | Pass |
| GitHub-hosted CI | Workflow written with PostgreSQL service, frozen dependencies, backend tests, frontend lint/typecheck/build | Configured; remote run not performed |
| Browser visual QA | Native browser connection unavailable | Not verified |

The actual HTTP readiness probe measured 7.67–37.81 ms after the first reconnecting request (2092.47 ms). These ten development requests are a foundation smoke result, not a retrieval or inference latency benchmark.

Initial installation/build attempts hit host memory pressure. The database image pull succeeded on retry. The production frontend build passed with Webpack, `experimental.cpus=1`, and `webpackMemoryOptimizations=true`. The local validation process also set `NODE_OPTIONS="--max-old-space-size=512 --max-semi-space-size=4"`; these heap limits are optional for development on a constrained machine.

The backend suite emits one upstream Starlette deprecation warning for its currently supported HTTPX TestClient compatibility layer. There are no test failures. No LLM inference, corpus retrieval, ingestion accuracy, citation fidelity, agent completion, container RAM target, or deployment result is claimed in Phase 0. Those measurements await their implementation phases.

Phase 0's local gates pass. GitHub execution and browser visual inspection are recorded as verification limits. Phase 1 may begin with PDF validation, layout-aware extraction, and traceable chunking.

## Phase 1, step 1: PDF pre-validation

Verification date: 15 November 2026. Scope: internal validation service and local CLI, before extraction.

| Check | Result |
| --- | --- |
| Focused PDF validation and CLI suite | 45 passed. Includes exact 20 MiB and 100-page boundaries, overflow rejection, misleading MIME/signature, unsafe names, encrypted/malformed PDFs, stream handling, and cleanup. |
| Full backend suite with real PostgreSQL | 65 passed with `RUN_DB_TESTS=1`; existing upstream Starlette/HTTPX deprecation warning only. |
| Backend lint, format, and strict types | Passed; mypy checked 18 source files. |
| Real-file CLI smoke | Supplied implementation guide accepted: 413,203 bytes, 17 pages, SHA-256 reported, UUID temporary file deleted. |
| Documentation | Local links and code fences validated. |

The validator uses `pypdf` for structural inspection and does not extract text. The upload API, layout-aware extraction, scanned-PDF detection, normalization, chunking, and restart recovery remain pending; Phase 1's full acceptance gate has not been reached. See the [step guide](<phases guide/phase-1/phase-1-step-1-pdf-validation.md>).

## Phase 1, step 2: Layout-aware extraction

Verification date: 15 November 2026. Scope: validation followed by internal page-by-page Markdown extraction and local JSON export.

| Check | Result |
| --- | --- |
| Full backend suite, real PostgreSQL enabled | 85 passed; existing upstream Starlette/HTTPX warning only. |
| Focused extraction and CLI checks | 23 cases passed before the final full-suite run, covering columns, tables, shaded code, blank pages, raw text, cleanup, errors, Unicode, and overwrite protection. |
| Backend lint/format/types | Ruff passed; 30 Python files formatted; strict mypy passed for 21 source files. |
| Real-file extraction | Guide: 17/17 nonblank pages, 33,946 Markdown characters, 59 Markdown table lines; source page labels and shaded code page checked. |
| Temporary-file cleanup | Staged PDF deleted after successful extraction and parser failures; image export disabled. |

The final implementation selects geometric layout mode after the default ONNX-backed mode encountered native allocation failure on the development host. Regression tests cover the in-memory removal of decorative text backgrounds outside tables, which corrected a real shaded-code content loss while retaining Markdown table output. No production memory, ten-paper parsing benchmark, or 98% text-retention result is claimed. Scanned-PDF detection and the remaining Phase 1 steps are pending. See the [step guide](<phases guide/phase-1/phase-1-step-2-layout-aware-extraction.md>).

## Phase 1, step 3: Scanned-PDF detection

Verification date: 15 November 2026. Scope: native-text density preflight, typed failed result, settings, CLI diagnostics, and cleanup.

| Check | Result |
| --- | --- |
| Full backend suite | 116 passed; two existing database integration tests skipped because Docker's engine was unavailable and real-database tests were not enabled. |
| Backend lint/format/types | Ruff passed; 32 Python files formatted; strict mypy passed for 22 source files. |
| Threshold boundaries | Exactly 50 characters is sufficient; exactly 80% low-text pages is accepted. Strict integer comparisons checked up to 100 pages. |
| Early abort | Ten rasterized text pages reject at page nine, before layout analysis, decorative cleanup, or OCR. |
| Mixed PDF and blank pages | Exactly 80% image-only pages can pass when the remaining page has sufficient text; source page order and low-text page metadata are retained. |
| Failure contract | CLI returns `status: "failed"`, `OCR_NOT_SUPPORTED`, safe density diagnostics, and exit code 2; no export is created. |
| Real guide extraction | 17 pages accepted, zero low-text pages, minimum readable count 748, temporary PDF deleted. |

The detector counts printable non-whitespace Unicode characters from the original text layer, so generated Markdown cannot inflate the count. An empty Markdown result for a sufficiently populated source page is a separate `PDF_EXTRACTION_FAILED` error. The existing Starlette/HTTPX warning remains nonblocking. No document row is persisted yet; future document/job integration must store the existing failed/error-code contract. Normalization, chunking, and recovery remain pending. See the [step guide](<phases guide/phase-1/phase-1-step-3-scanned-pdf-detection.md>).

## Phase 1, steps 4-6: Normalization, chunking, and recovery

Verification date: 16 November 2026. Scope: internal preparation pipeline and durable startup recovery; representative-corpus acceptance remains separate.

| Check | Result |
| --- | --- |
| Unit/general suite | 141 passed; six database cases reserved for a separate run. |
| Real PostgreSQL suite | Six passed with `RUN_DB_TESTS=1` and `--noconftest tests/integration`; 147 distinct tests passed across both runs. |
| Ruff and mypy | Lint/format passed for 48 Python files; strict types passed for 33 application/migration files. |
| Migration | Local PostgreSQL upgraded to `0002_documents`; Alembic reports no pending model operations. |
| Normalization | Running boundary text removed conservatively; protected Markdown and labelled body text retained; raw Unicode/CRLF mappings checked character by character. |
| Chunking | Actual offline token counts, ordinary-prose overlap, stable IDs, source ranges, complete normalized coverage, whole tables/code, oversized atomic flags, and Unicode/long words verified. |
| Recovery | Stale/strict-five-minute/fresh/terminal cases, idempotence, committed lifespan recovery, per-process execution, and 12 concurrent readiness probes verified. |
| Real guide preparation | 17 pages, 17 chunks, 17 removed boundary lines, no oversized chunks; every raw offset valid and all normalized non-whitespace text covered; temporary PDF deleted. |

Windows virtual-memory exhaustion interrupted initial combined test attempts. Running unit tests with Docker stopped and the lightweight database-only suite after restarting Docker resolved verification without closing unrelated applications. A Linux test-container attempt was also interrupted and is not counted as successful validation. The existing Starlette/HTTPX warning remains nonblocking.

The offline tokenizer uses bundled, checksummed OpenAI `cl100k_base` vocabulary with its MIT license. Python configuration now consistently targets 3.12, matching the existing runtime, CI, and image. Normal-prose chunks target 600-800 tokens; page tails can be shorter and indivisible tables/code can exceed the maximum. At this Phase 1 checkpoint, no ten-paper/98%-retention result, embedding index, public upload workflow, or production memory claim was made.

## Phase 2, steps 3-5: PDF indexing, session idempotency, deletion, and expiry cleanup

Verification date: 18 November 2026. Scope: local PDF embedding/indexing, session/checksum persistence idempotency, owner-scoped document deletion, and periodic expired-session cleanup.

| Check | Result |
| --- | --- |
| Backend suite with real PostgreSQL | 183 passed with `RUN_DB_TESTS=1`, including the indexing CLI tests. |
| Local PDF CLI smoke | The supplied 17-page guide produced 27 chunks with 384-dimensional BGE embeddings. Two persistence runs using one session ID returned the same document ID; the database contained one document, one batch, and 27 chunks. Temporary smoke data was deleted. |
| Lifecycle coverage | Same-session duplicate indexing (including concurrent calls) returns one document and creates one batch/chunk set; another session may index the same checksum. |
| Deletion and isolation | Missing session cookie returns 401; another session's document returns 404; owner deletion cascades to batch and chunk rows. |
| Expiry worker | Lifespan starts the worker; strict `expires_at < NOW()` deletes expired session documents, preserves the equality boundary, and excludes samples. |
| Migration | `0004_session_lifecycle` applied; `alembic check` reports no pending model operations. |
| Ruff, formatting, and types | `ruff check .` and `ruff format --check .` pass; mypy passes for 47 application/migration source files. |

No public PDF upload endpoint exists yet, so browser upload/deduplication is not exercised end to end. Session-scoped retrieval was added in Phase 3 and its integration test verifies query isolation. See the [step 3 guide](<phases guide/phase-2/phase-2-step-3-vector-fts-indexes.md>), [step 4 guide](<phases guide/phase-2/phase-2-step-4-session-idempotency-deletion.md>), and [step 5 guide](<phases guide/phase-2/phase-2-step-5-expired-session-cleanup.md>).

## Phase 3: Session-scoped retrieval and evaluation

Verification date: 20 November 2026. Scope: fixed 40-question set, three attributed sample PDFs, session-scoped cosine retrieval, API route, metric calculation, and out-of-corpus cutoff calibration.

| Check | Result |
| --- | --- |
| Sample corpus | All three CC BY 4.0 PDFs indexed; manifest checksums and page counts validated. |
| Golden set | 40 questions validated: 30 answerable page-labeled items and 10 out-of-corpus items. |
| Retrieval/API | `POST /api/v1/search` implemented; PostgreSQL integration coverage verifies sample/current-session scope, foreign-document rejection, and missing-cookie rejection. |
| Retrieval quality | Recall@5 **0.767** (target ≥0.80); Precision@5 **0.300** (target ≥0.60); MRR **0.602** (target ≥0.70). **Not met.** |
| Out-of-corpus detection | **90%** (9/10; target ≥90%). Similarity cutoff: **0.5671493153**; no answerable queries fell below it in this set. |
| Warm query latency | p95 **73.52 ms** (target ≤800 ms), including query embedding and database retrieval; model/process cold start excluded. |

The evaluation command is `uv run --project apps/api python scripts/run_retrieval_eval.py` from the repository root. Full reproducible output is in [retrieval_metrics.json](../data/eval/retrieval_metrics.json). The implementation and calibration workflow are in the [Phase 3 guide](<phases guide/phase-3/README.md>).

Phase 3's implementation is present, but its overall quantitative acceptance gate **does not pass** because Recall@5, Precision@5, and MRR are below target. Do not treat the calibration and latency passes as a full-phase acceptance. Improve retrieval ranking or review the page-level labels, then rerun the fixed benchmark before claiming the quality gate is met.

### Retrieval model experiments

The following exploratory tests used the same 30 answerable questions, page labels, and metric definitions. Alternative embeddings were computed over the 153 indexed chunk texts offline; they were not persisted or tested through the API. None met the retrieval-quality targets:

- `Xenova/bge-base-en-v1.5` int8: Recall@5 **0.750**, Precision@5 **0.287**, MRR **0.581**.
- `Xenova/bge-large-en-v1.5` int8: Recall@5 **0.783**, Precision@5 **0.293**, MRR **0.607**.
- `Xenova/e5-large-v2` int8: Recall@5 **0.800**, Precision@5 **0.287**, MRR **0.606**.
- `Xenova/bge-reranker-base` int8 reranking the dense top 20: Recall@5 **0.783**, Precision@5 **0.300**, MRR **0.694**; measured warm p95 was **12.95 s**, above the 800 ms limit.

`Qdrant/Qwen3-Embedding-0.6B-onnx` int8 was also smoke-tested locally: a 24-token query took about **2.8–3.4 s** on CPU, so it was not run through the full evaluation. No experimental model was adopted; the database-backed BGE-small results above remain the official benchmark.
