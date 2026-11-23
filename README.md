# Agentic Research & Knowledge Assistant

A research workspace for evidence-grounded answers across PDFs. Implementation follows the supplied v2.0 guide, one acceptance gate at a time.

Phase 0 builds the project foundation: Next.js/TypeScript, FastAPI, validated configuration, structured request logs, async PostgreSQL pooling, pgvector migrations, and CI. All six Phase 1 implementation steps provide validation, extraction, normalization, traceable chunking, and database-backed recovery. Phase 2 adds an internal PDF embedding/indexing CLI, session idempotency, deletion, and expiry cleanup. Phase 3 adds session-scoped dense retrieval and a quantitative benchmark. Phase 4 adds grounded answer generation, schema validation, citation verification, and evidence fallback. The Phase 3 retrieval-quality targets remain unmet, and Phase 4 acceptance awaits the full live-model evaluation and manual audit; see the [evaluation report](docs/evaluation-report.md).

## Requirements

- Docker with Compose, running Linux containers
- Python 3.12 via [uv](https://docs.astral.sh/uv/)
- Node.js 20.9+ (Node 22 recommended) and npm

## Start locally

Run from the repository root. On Windows, use PowerShell.

```powershell
Copy-Item .env.example .env
docker compose up -d --wait db
```

If `.env` already exists, keep it. It is ignored by Git. Set `POSTGRES_PASSWORD` and the matching password in `DATABASE_URL` before starting a fresh database. Compose exposes PostgreSQL on `127.0.0.1:15432` by default (`DB_PORT` is configurable). Keep the port in `DATABASE_URL` consistent. Windows can reserve ports, including the previously used55432; choose an available port if Docker reports access denied. Data lives in a named Docker volume and survives container restarts.

Generation now defaults to Groq's `openai/gpt-oss-120b` in the example configuration. Set `HOSTED_LLM_API_KEY` in the root `.env` before starting the backend. The provider URL is `https://api.groq.com/openai/v1`; embeddings remain local BGE. For optional Ollama inference, set `LLM_PROVIDER=local` instead. See the [Groq configuration guide](<docs/phases guide/phase-4/quality-improvements/groq-hosted-generation.md>) for verification and measured pilot results.

In one terminal:

```powershell
cd apps/api
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

In another:

```powershell
cd apps/web
npm ci
npm run dev
```

Open http://localhost:3000. API documentation is at http://127.0.0.1:8000/docs.
The backend reads the root `.env` regardless of working directory. The frontend defaults to `http://localhost:8000`; copy `apps/web/.env.example` to `apps/web/.env.local` to change it. Use `http://localhost:3000` for the frontend because that is the default allowed CORS origin.

`EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `LLM_PROVIDER`, and `DATABASE_URL` are required. Local provider settings do not load models in Phase 0. Hosted providers require their server-side keys and model configuration. Production settings enforce hosted inference and API embeddings. Public frontend configuration contains only the API base URL.

## Verify the foundation

To try the PDF validator from `apps/api`, run:

```powershell
uv run python -m app.services.ingestion.cli 'C:\path\to\paper.pdf'
```

The command checks the PDF filename, MIME declaration, signature, actual size, structure, encryption, and page count. It returns JSON and deletes its UUID-named temporary copy. See the [Phase 1 step 1 guide](<docs/phases guide/phase-1/phase-1-step-1-pdf-validation.md>) for the service interface, error codes, and focused tests.

To extract page-by-page Markdown, add `--extract`. Optionally save the result to a new UTF-8 JSON file:

```powershell
uv run python -m app.services.ingestion.cli 'C:\path\to\paper.pdf' --extract --output '.\pages.json'
```

The pipeline validates first, preserves page numbers and Markdown tables, and deletes its temporary PDF. Existing output files are not overwritten. See the [Phase 1 step 2 guide](<docs/phases guide/phase-1/phase-1-step-2-layout-aware-extraction.md>) for geometric layout mode, shaded-text handling, results, and tests.

Extraction first checks text density: fewer than 50 readable characters makes a page low-text, and more than 80% low-text pages produces `status: "failed"` with `OCR_NOT_SUPPORTED`. Accepted results include a per-page density report. Optional settings are `MIN_TEXT_CHARS_PER_PAGE` and `MAX_LOW_TEXT_PAGE_PERCENT`. See the [Phase 1 step 3 guide](<docs/phases guide/phase-1/phase-1-step-3-scanned-pdf-detection.md>) for boundaries, early abort, mixed PDFs, and the failure contract.

To normalize repeated page-boundary text and generate traceable chunks, use `--prepare`:

```powershell
uv run python -m app.services.ingestion.cli 'C:\path\to\paper.pdf' --prepare --output '.\prepared.json'
```

Preparation retains original Markdown, adds normalized-to-source mappings, and targets 600-800 real tokens with up to 100-token overlap. Tables and fenced code stay whole; short page tails and oversized atomic blocks are documented exceptions. The tokenizer vocabulary is bundled for offline use. Settings are `CHUNK_MIN_TOKENS`, `CHUNK_MAX_TOKENS`, and `CHUNK_OVERLAP_TOKENS`. See the [normalization](<docs/phases guide/phase-1/phase-1-step-4-deterministic-normalization.md>) and [chunking](<docs/phases guide/phase-1/phase-1-step-5-markdown-aware-chunking.md>) guides.

Migration `0002_documents` adds persistent ingestion status. After applying migrations, API startup marks queued/processing records last updated more than five minutes ago as failed with `INTERRUPTED_BY_RESTART`, once per process. See the [recovery guide](<docs/phases guide/phase-1/phase-1-step-6-crash-safe-recovery.md>). The Phase 1 CLI does not enqueue or persist jobs/chunks.

## Test Phase 2 with a PDF

The Phase 2 CLI embeds a local PDF and prints a summary without writing to the database:

```powershell
cd apps/api
uv run python -m app.services.indexing.cli 'C:\path\to\paper.pdf'
```

For local CPU embeddings, install the optional ONNX runtime group if needed:

```powershell
uv sync --frozen --group local-embeddings
```

The first local run may download the pinned BGE tokenizer/model. To persist the document as session-owned and test idempotency, ensure PostgreSQL is running and migrations are current:

```powershell
uv run alembic upgrade head
$sessionId = [guid]::NewGuid().ToString()
$pdf = 'C:\path\to\paper.pdf'
$first = (uv run python -m app.services.indexing.cli $pdf --persist --session-id $sessionId) | ConvertFrom-Json
$second = (uv run python -m app.services.indexing.cli $pdf --persist --session-id $sessionId) | ConvertFrom-Json
$first.document_id
$second.document_id
```

Both runs should report the same `document_id`; the second run re-embeds the file but does not insert a second document, batch, or chunk set. Use `--persist --sample` instead to add a global sample. `--output '.\paper-embeddings.json'` exports chunk text, provenance, and vectors to a new file; treat that export as sensitive and do not overwrite an existing file.

See the [Phase 2 step 3 guide](<docs/phases guide/phase-2/phase-2-step-3-vector-fts-indexes.md>) for database verification and session-scoped deletion commands.

## Run the Phase 3 retrieval baseline

The three sample PDFs and 40-question gold set are licensed CC BY 4.0 and attributed in `data/samples/README.md`. From the repository root, index the samples and run the evaluation:

```powershell
cd apps/api
uv run alembic upgrade head
uv run python -m app.services.indexing.seed_samples
cd ..\..
uv run --project apps/api python scripts/run_retrieval_eval.py
```

The runner writes measured Recall@5, Precision@5, MRR, p95 query latency, and the out-of-corpus similarity cutoff to a new timestamped report, or a fresh path supplied with `--output`. Existing reports are never overwritten. `--mode dense` and `--mode hybrid` compare strategies using the same dataset; `--dataset` selects an explicit label set. The API's `POST /api/v1/search` marks evidence insufficient when the maximum returned cosine is at or below `RETRIEVAL_SIMILARITY_THRESHOLD`; it does not generate an answer. Dense remains the default because the measured hybrid variant reduced recall/precision despite improving MRR. See the [evaluation report](docs/evaluation-report.md).

## Run grounded answer evaluation

Start the API with PostgreSQL and the sample corpus available. The current generation configuration is `LLM_PROVIDER=hosted`, `HOSTED_LLM_MODEL=openai/gpt-oss-120b`, and `HOSTED_LLM_BASE_URL=https://api.groq.com/openai/v1`, with the key stored locally in `HOSTED_LLM_API_KEY`. Hosted inference sends selected document excerpts to Groq.

For optional local inference, set `LLM_PROVIDER=local`, configure Ollama, and pull the model:

```powershell
ollama pull llama3.2:3b
```

Other OpenAI-compatible hosted endpoints remain configurable through the same server-side settings.

From the repository root, create a new Phase 4 evaluation report:

```powershell
uv run --project apps/api python scripts/run_grounded_qa_eval.py --output data/eval/phase4-review.json
```

The runner sends all 40 fixed questions through `POST /api/v1/answer`, checks citation-to-context validity and out-of-corpus abstention, and creates a 30-answer human faithfulness review packet. Mark each `manual_claim_audit[].faithful` as `true` or `false` after checking the cited claims against the returned evidence, then score to a separate file:

```powershell
uv run --project apps/api python scripts/run_grounded_qa_eval.py --score-audit data/eval/phase4-review.json --output data/eval/phase4-review-scored.json
```

The runner refuses to overwrite output files. Its version 2 report retains all HTTP outcomes, validates response schemas and source quotes, records exact used context, and prevents failed/degraded requests from appearing to pass. See the [Phase 4 step guides](<docs/phases guide/phase-4/README.md>) and [six quality improvement guides](<docs/phases guide/phase-4/quality-improvements/README.md>) for the full gates. Deterministic provider tests do not establish live-model faithfulness. The latest full local run failed answer quality despite recovered runtime availability. Groq now passes the benchmark-list, dataset-count, and table-lookup pilot cases; the comparison pilot still abstains, and the full hosted evaluation remains pending. See the evaluation report.

From `apps/api`:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run alembic check
uv run pytest -q
```

Run the real database integration tests explicitly:

```powershell
$env:RUN_DB_TESTS = "1"
uv run pytest -q
```

On macOS/Linux, use `RUN_DB_TESTS=1 uv run pytest -q`.
With the API running, execute `python scripts/check_health.py` from the repository root for ten actual HTTP readiness checks. A failure exits nonzero.

From `apps/web`:

```powershell
npm run lint
npm run typecheck
npm run build
```

The GitHub Actions workflow runs the same checks on clean Linux runners, with a real pgvector PostgreSQL service and migrations applied before integration tests. A GitHub-hosted run requires pushing the repository; local results are recorded in [the evaluation report](docs/evaluation-report.md).

Local result: **20 backend tests passed**, including real database integration; **10/10 live HTTP readiness checks passed**. Frontend lint, route type generation, type checks, and production build passed. Four frontend routes returned HTTP 200. The native browser preview connection was unavailable, so visual interaction and layout were not inspected. GitHub-hosted CI has not been run.

The build uses Webpack with one worker and memory optimizations to accommodate this development machine. On a memory-constrained Windows host, optionally set `$env:NODE_OPTIONS = "--max-old-space-size=512 --max-semi-space-size=4"` before frontend commands.

## Health and logs

| Endpoint | Meaning |
| --- | --- |
| `GET /api/v1/health/live` | Process liveness; HTTP 200 even when PostgreSQL is unavailable. |
| `GET /api/v1/health` | Readiness; HTTP 200 only after a live database connection, vector operator check, and migration revision check. HTTP 503 when unavailable. |

Readiness reports the embedding model and LLM provider configuration; it does not claim a model inference check. Both health responses disable caching. Database outages are bounded by a configurable timeout and recover on subsequent health requests. Schema changes happen through Alembic, never automatically on API startup.

Application logs are JSON with a UUID `request_id`, timestamp, event, route template, method, status, and latency. `X-Request-ID` is returned to callers; valid incoming UUIDs are preserved. Query strings, raw exception messages, credentials, uploaded text, and request bodies are excluded. Run uvicorn with `--no-access-log` to avoid separate access logs containing query strings.

## Layout

- `apps/web`: frontend shell, typed health client, workspace and library routes
- `apps/api`: API, typed settings, pooling, migrations, unit/integration tests, lean Dockerfile
- `data/{samples,eval,fixtures}`: reserved for licensed corpus and evaluation fixtures
- `scripts/check_health.py`: live acceptance probe
- `docs`: architecture, contracts, threat model, evaluation evidence
- `.github/workflows/ci.yml`: backend and frontend gates

Placeholder directories preserve the guide's structure without pretending later-phase services are implemented. The supplied guide remains unchanged.

## Stop and restart

Stop terminal servers with Ctrl+C. `docker compose stop` stops the project database without deleting data; `docker compose up -d --wait db` starts it again. The database uses `restart: unless-stopped` so Docker can restart it after an unexpected exit or a Docker restart; an explicitly stopped container stays stopped until started again. If readiness reports `db: "unavailable"`, check `docker compose ps -a` and start the database before retrying. Do not remove the named volume unless you intend to erase this project's database. For the API image, build with `docker build -t research-api apps/api`, then run migrations and the API with your environment supplied externally. Never bake `.env` into an image.

See [architecture](docs/architecture.md), [API contracts](docs/api-contracts.md), and [security boundaries](docs/threat-model.md). The Phase 1 representative-corpus acceptance benchmark remains pending. Phase 2 indexing/lifecycle work and Phase 3 scoped retrieval are implemented, but Phase 3's measured quality targets are not all met. Phase 4 answer generation is implemented with mock-tested safeguards; live-model acceptance remains pending. The Phase 7 sample workspace, citation drawer, readiness banner, and research timeline are implemented; private PDF upload and OCR rejection are now implemented and tested. See the [Phase 2 guides](<docs/phases guide/phase-2/README.md>), [Phase 3 guides](<docs/phases guide/phase-3/README.md>), [Phase 4 guides](<docs/phases guide/phase-4/README.md>), and [Phase 7 guides](<docs/phases guide/phase-7/README.md>) for scope and verification status.

For the Phase 0 changes, detailed file structure, startup flow, and component responsibilities, read the [Phase 0 project foundation guide](<docs/phases guide/phase-0/phase-0-project-foundation.md>).

## Phase 5 implementation

SQL Hybrid RRF, source-preserving adjacent context, optional quantized CPU reranking, and a frozen-input three-mode ablation are implemented. Separate [Phase5 step guides](<docs/phases guide/phase-5/README.md>) document the source files, runtime behavior, commands, and measured results. The hybrid quality-gain acceptance target is **unmet**; dense remains the default, and `ENABLE_RERANKER=false` remains the free-tier default. Worker-only memory measurements do not establish deployment-wide RAM usage.

Run `uv run --project apps/api python scripts/run_phase5_ablation.py` from the root to create a new report. It exits nonzero when measured acceptance fails and preserves existing reports.

## Phase 7 frontend

The web app includes an actionable cold-start readiness banner, preselected
sample-paper questions, exact-source citation drawers, and a live research-job
timeline. See the [Phase 7 step guides](<docs/phases guide/phase-7/README.md>)
for visual verification instructions and acceptance limitations. The browser
workflow uses deterministic mocked responses; it does not claim live-model
answer quality. The completed UI adds a private PDF library, working uploads with
OCR/size/type feedback, Unicode-safe inline citations, and bounded loading states.
Typography and icons are bundled locally; transitions respect reduced motion.
See [verification](<docs/phases guide/phase-7/verification.md>) for measured results.
