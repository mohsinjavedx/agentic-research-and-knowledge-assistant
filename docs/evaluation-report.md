# Phase 0 acceptance report

Latest Phase5 evidence is documented in the [Phase5 ablation guide](<phases guide/phase-5/phase-5-step-4-ablation.md>). All four implementation steps are present, but the measured quality-gain gate is unmet. On the unchanged40-question dataset: dense Recall@5=0.7667/MRR=0.6244, SQL Hybrid=0.7667/0.6078, and Hybrid+TinyBERT=0.7833/0.5694. Hybrid SQL p95=17.64ms and incremental benchmark-worker RSS=1.95MB; database/container memory is unmeasured. Dense and reranker-off remain defaults. The earlier phase evidence below is retained as historical evidence, not overwritten.

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

## Phase 4: Grounded answer generation and schema enforcement

Verification date: 20 November 2026. Scope: session-scoped `POST /api/v1/answer`, XML-escaped untrusted evidence prompting, Instructor/Pydantic response validation, deterministic citation verification, weak-evidence abstention, and timeout/429 evidence fallback.

| Check | Result |
| --- | --- |
| Focused generation/API tests | **12 passed** across PDF prompt escaping, fabricated/misaligned citations, abstention, fallback, session-cookie enforcement, and sanitized provider errors. |
| Citation verification | Implemented as an allowlist over the request's retrieved chunk IDs and exact document/page metadata; invalid citations are removed, and an answer with no valid citations is discarded. |
| Out-of-corpus abstention | Shares the Phase 3 calibrated similarity threshold and skips LLM calls for weak/no retrieval. The existing Phase 3 out-of-corpus rate is **90% (9/10)**; the Phase 4 live API evaluation has not yet been run. |
| Manual citation-claim support | **Not measured.** The required 30 generated answers and human audit are pending. |
| Live prompt-injection behavior | **Not measured.** Unit tests verify XML escaping and the system instruction; the end-to-end model attack scenario is pending. |
| Live provider/fallback | Timeout and 429 fallback behavior is tested with a fake provider. No Ollama process/model or hosted LLM credentials were available for a live-provider run. |

The reproducible 40-question run and 30-answer manual audit are documented in the [Phase 4 step 4 guide](<phases guide/phase-4/phase-4-step-4-fallback-evaluation.md>). Run `uv run --project apps/api python scripts/run_grounded_qa_eval.py --output <new-report-path>` from the repository root against a running API. The Phase 4 acceptance gate is **incomplete**, not passed: live abstention must reach ≥90%, programmatic citations must remain 100% valid, at least 27/30 manually audited answers must be faithful, and the live injection test must resist the malicious evidence instruction.

### Phase 4 local-provider follow-up

Verification date: 21 November 2026. Runtime: PostgreSQL ready, sample document `35d86749-bf13-55ac-8008-231937b43bab` ready, and local Ollama model `llama3.2:3b` available.

| Check | Result |
| --- | --- |
| Search path | The same query/document request returned five retrieved chunks; API health reported the database connected. |
| Small local completion | Ollama returned a short unstructured response in 3.00 s. |
| Minimal structured response | Instructor/Pydantic structured generation with one short synthetic evidence passage succeeded in 22.18 s and returned one citation. This is a provider smoke test, not an answer-quality result. |
| Five-chunk answer request | One live API request took 47.19 s total: scope 13.71 ms, query embedding 14.28 ms, vector search 16.17 ms, and generation 47.14 s. It returned HTTP 200 with `degraded_mode: true` and all five evidence chunks after the configured 45 s model timeout. |
| One-chunk answer request | One live API request took 42.86 s and returned an insufficient-evidence abstention with no citations. |
| Full-context structured call | A direct structured call with the five retrieved chunks exceeded a 120 s timeout. |

The timeout had been wrapped in an Instructor retry exception whose `failed_attempts` list was empty, while its cause chain contained `openai.APITimeoutError` and `httpx.ReadTimeout`. The provider previously checked only `failed_attempts`, misclassified the timeout as a generic provider error, and returned HTTP 503. It now also checks the exception cause/context chain, so the endpoint uses its intended HTTP 200 evidence fallback. Regression coverage is in [test_llm_provider.py](../apps/api/tests/unit/test_llm_provider.py) and [test_answer_api.py](../apps/api/tests/unit/test_answer_api.py).

These are individual diagnostic runs, not a latency benchmark. The timeout mapping is fixed, but this local model/context did not produce a usable answer for the tested real query; generated-answer quality, the 30-item manual audit, and live prompt-injection acceptance remain unverified. Phase 4 acceptance is still incomplete.

### Five-benchmark answer and missing-citations fix

Verification date: 21 November 2026. The reported request asked which five benchmarks evaluate the educational question-answering system, restricted to document `35d86749-bf13-55ac-8008-231937b43bab` with `top_k: 5`. Its first retrieved passage already contained the answer on page 7. The original local provider reproduced a timeout after 92.16 seconds; the empty answer citations were the intentional evidence-only fallback, not missing retrieval results.

The local adapter previously called `/v1/chat/completions` with an unsupported `options.num_ctx` parameter. Ollama's active context was 4096 despite `OLLAMA_NUM_CTX=2048`. The adapter now calls native `/api/chat`, applies `num_ctx`, bounds local output with `LLM_MAX_OUTPUT_TOKENS=512`, and selects a leading prefix of whole source passages using a conservative input estimate. With this request and the default 2048-token context, the model receives the first complete passage; all five retrieved passages remain in the HTTP response. Increasing context may be necessary for questions requiring several passages.

A native diagnostic returned the correct benchmark names but a one-based source index of `1` for the sole source `0`. This was rejected. The native request's JSON schema now enumerates only the supplied source indices, with an independent bounds check after generation. No source index is guessed or remapped.

The exact original body was then submitted to the running `/api/v1/answer` using a fresh anonymous session and the actual database, embedding provider, and Ollama model. Verified result:

- HTTP **200** in **14.40 seconds**, including **13.34 seconds** generation. This is a single diagnostic, not a latency benchmark.
- Answer: **AI2_ARC, OpenBookQA, E-EVAL, Textbook Question Answering (TQA), and ScienceQA**.
- One citation to chunk `4777fae4-cc65-5989-b217-0b40e0e91031`, the requested document, **page 7**.
- `degraded_mode: false`, `insufficient_evidence: false`, five retrieved evidence passages retained.
- Ollama `/api/ps` confirmed the active model context was **2048** after the native request.
- Backend suite: **203 passed, 16 skipped**. The skipped database integration cases were not rerun for this provider-only change. Native transport tests cover actual request options/schema, whole-source budgeting, citation bounds, incomplete/malformed output, sanitized failures, rate limits, and cancellation at the total deadline. Configuration tests reject local output reservations equal to or larger than the context. Ruff lint/format checks and mypy also passed.

The local model still has finite context and output limits; other questions can abstain or fail safely. The full 40-question Phase 4 run, 30-answer human audit, and live model injection gate remain pending. This fixes the reported request without establishing full-phase acceptance.

### Subsequent answer quality implementation

Verification date: 21 November 2026. Scope: source-label audit, optional hybrid retrieval, complete focused excerpts, checked source quotes, explicit used context, and a failure-aware answer evaluator. The earlier successful 14.4-second smoke result above predates these changes and is not validation of this new generation contract.

An independent source-PDF audit covered all 30 answerable questions without using retrieval rankings. Only `education-single-01` required correction: page 8 to page 7. All other adequate page sets were retained, as were all 10 out-of-corpus questions. The audit flags duplicate MPT-7B-Instruct rows in the medical paper's Table 4 rather than inventing a single value. Original dataset bytes are preserved in [golden_set.v1.json](../data/eval/golden_set.v1.json); source excerpts/reasons are in [the label audit](../data/eval/label-audit-2026-11-21.json). The original retrieval report remains unchanged.

Two actual PostgreSQL retrieval runs used the same corrected dataset revision/hash:

- [Corrected dense](../data/eval/retrieval-corrected-dense-2026-11-21.json): Recall@5 **0.7667**, Precision@5 **0.3000**, MRR **0.6244**, warm retrieval p95 **45.21 ms**.
- [Corrected hybrid](../data/eval/retrieval-corrected-hybrid-2026-11-21.json): Recall@5 **0.7500**, Precision@5 **0.2800**, MRR **0.7250**, warm retrieval p95 **121.64 ms**.

Both retain calibrated 90% out-of-corpus detection, but neither meets the complete retrieval gate. Hybrid is implemented and selectable with `RETRIEVAL_MODE=hybrid`; dense remains the default because hybrid reduced recall and precision. Cosine and fusion scores remain separate, and maximum cosine drives abstention regardless of fusion ordering. These results are fixed-set comparisons, not held-out validation.

The generation pipeline now selects complete source blocks and returns the actual supplied excerpt mapping. Public citations include original-source quotes and character ranges; citation claims must match answer text, and every non-whitespace character must be covered. Native and hosted adapters return this context alongside their structured draft. These checks establish source provenance and answer coverage, not semantic entailment.

Final verification:

- **251 passed** in the full backend suite with `RUN_DB_TESTS=1`, including PostgreSQL isolation/keyword recall and all generation/provider/API/evaluator tests.
- Ruff lint/format passed for the backend and both changed evaluation scripts; mypy passed for **65** source files; `git diff --check` passed.
- A fresh code review found three Important issues: blank-line-separated lists, uncovered meaning-bearing symbols, and malformed HTTP 200 responses counted as successes. Each was reproduced with failing tests, fixed, and included in the final passing suite. The context-mapping docstring was corrected as part of documentation.
- An earlier combined run had a resource-sensitive three-second timeout in `test_health_checks_do_not_repeatedly_fail_jobs_after_startup`; the final complete run passed without changing that timeout or weakening the test.

The [40-question live answer run](../data/eval/answer-quality-review-2026-11-21.json) completed and correctly **failed** acceptance: **31 HTTP 503 failures**, **9 successful pre-generation abstentions**, **0/30 generated answerable completions**, and **no generated citations**. Citation validity is unmeasured, not a vacuous 100%; all 30 manual verdicts remain unset. Out-of-corpus abstention was 9/10. Failed-request latency is not a successful-answer latency benchmark.

Direct native diagnostics and Ollama's server log showed model-loading allocation failures while Windows had approximately **786 MB free virtual memory**. A normal load failed allocating a 649 MB buffer; an isolated mmap/batch diagnostic still failed allocating a 1.36 GB CPU_REPACK buffer. No model/hardware upgrade, OS memory setting, unrelated application shutdown, or persistent runtime option change was applied. Thus, live quality and model-level injection acceptance remain blocked by runtime capacity and must be rerun with sufficient resources. No improvement in live answer correctness or faithfulness is claimed from the deterministic tests.

The implementation and each improvement step are documented in the [quality improvement guides](<phases guide/phase-4/quality-improvements/README.md>). The current software checks pass; overall Phase 4 quality acceptance remains incomplete.

### Live retry after freeing memory

Verification date: 21 November 2026. The user closed applications and requested the same 40-question evaluation again. Free virtual memory before the retry was approximately **6.5 GB**, compared with about 786 MB during the previous run. The API/database readiness check passed, Ollama loaded `llama3.2:3b` with context 2048, and roughly 3.9 GB of virtual memory remained after loading. No application code, model, context limit, retrieval mode, or prompt was changed for this retry. The dataset hash matches the previous run.

The new, preserved [retry report](../data/eval/answer-quality-review-2026-11-21-retry-1.json) records:

- **40/40 HTTP 200**, zero recorded errors, and zero degraded responses. The model-allocation failure did not recur.
- **1/30 cited answerable completions** (3.33%, target at least 90%); **29/30 answerable questions abstained** despite completed generation context being present.
- **10/10 correct out-of-corpus abstentions**.
- **1/1 citation passed provenance checks**. This does not establish semantic support or answer correctness.
- Summed request duration **20.07 minutes**; nearest-rank p95 API request latency **57.13 seconds**. These include abstentions and are not successful-answer-only latency measurements.
- Overall acceptance **failed**. The 30-item human audit remains unset; no manual faithfulness pass is claimed.

An agent spot-check found that the sole cited answer, `education-single-02`, was incorrect: it says E-EVAL contains **4** multiple-choice questions and quotes `4.3 E-EVAL experimental results`, a section heading on page 14. The source audit on page 8 gives **4,351**. The correct value occurs in this request's full retrieved evidence, but not in its actual `used_evidence`. This identifies a concrete evidence-selection/context-packing failure and demonstrates that quote provenance alone does not establish entailment. The raw report and manual-review fields were not modified to disguise this failure.

The original five-benchmark question also abstained, although its used page 7 excerpt contains the complete five-name list. Its response alone does not distinguish a model insufficiency verdict from a citation/coverage rejection; further diagnostics are needed before assigning that cause.

Runtime availability has recovered, but answer quality has not. The next quality work is to retain answer-bearing evidence during selection/packing and check actual claim support; the existing software-test pass must not be described as a live answer-quality pass.

### Groq generation switch and live pilot

Verification date: 21 November 2026. At the user's request, generation was switched from local `llama3.2:3b` to hosted Groq `openai/gpt-oss-120b` using the existing OpenAI-compatible adapter. The configured key successfully accessed Groq's models endpoint and the requested model was available. The root `.env` was updated, the key preserved, and the running backend reloaded. Health confirmed hosted generation and a connected database. Embeddings/retrieval stayed local, with dense retrieval still the default.

The original five-benchmark request returned a correct complete sentence with the five names, a page7 citation, and an exact checked source quote in **3.15 seconds**, of which approximately **1.68 seconds** was generation. Both insufficiency and degraded flags were false. Five focused excerpts reached the hosted model. The [preserved smoke report](../data/eval/groq-gpt-oss-120b-benchmark-smoke-2026-11-21.json) contains the exact request and response.

The [additional pilot report](../data/eval/groq-gpt-oss-120b-pilot-2026-11-21.json) records four more HTTP200 cases: the E-EVAL count was correctly **4,351** with a checked quote (1.39s); the OpenBookQA table accuracy was correctly **93.2%** with a checked quote (1.54s); the comparison question still abstained (1.13s); and the out-of-corpus question correctly abstained (0.12s). All returned quote offsets matched their retrieved source strings.

This verifies the requested provider switch and three factual answers, not full Phase4 acceptance. The hosted40-question benchmark and formal30-answer faithfulness audit have not yet been rerun. The hosted path supplies all focused passages while local context packing can omit some, so these pilot results do not isolate model capability from context differences. No source selection or validation behavior was changed during this provider switch.
