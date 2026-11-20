# Agentic Research & Knowledge Assistant

A research workspace for evidence-grounded answers across PDFs. Implementation follows the supplied v2.0 guide, one acceptance gate at a time.

Phase 0 builds the project foundation: Next.js/TypeScript, FastAPI, validated configuration, structured request logs, async PostgreSQL pooling, pgvector migrations, and CI. All six Phase 1 implementation steps provide validation, extraction, normalization, traceable chunking, and database-backed recovery. Phase 2 adds an internal PDF embedding/indexing CLI, session idempotency, deletion, and expiry cleanup. Phase 3 adds session-scoped dense retrieval and a quantitative benchmark. The current retrieval baseline does not yet meet all quality targets; see the [evaluation report](docs/evaluation-report.md). Public upload UI, grounded answer generation, agent workflows, and cloud deployment remain later work.

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

If `.env` already exists, keep it. It is ignored by Git. Set `POSTGRES_PASSWORD` and the matching password in `DATABASE_URL` before starting a fresh database. Compose exposes PostgreSQL on `127.0.0.1:55432` to avoid common local database conflicts. Data lives in a named Docker volume and survives container restarts.

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

The runner writes measured Recall@5, Precision@5, MRR, p95 query latency, and the out-of-corpus similarity cutoff to `data/eval/retrieval_metrics.json`. The API's `POST /api/v1/search` returns page citations and marks evidence insufficient when the best cosine similarity is at or below `RETRIEVAL_SIMILARITY_THRESHOLD`; it does not generate an answer. The current baseline meets the out-of-corpus and latency targets, but not the three retrieval-quality targets; see the [evaluation report](docs/evaluation-report.md).

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

See [architecture](docs/architecture.md), [API contracts](docs/api-contracts.md), and [security boundaries](docs/threat-model.md). The Phase 1 representative-corpus acceptance benchmark remains pending. Phase 2 indexing/lifecycle work and Phase 3 scoped retrieval are implemented, but Phase 3's measured quality targets are not all met. Public upload UI, grounded generation, and later-phase workflows remain outstanding. See the [Phase 2 guides](<docs/phases guide/phase-2/README.md>) and [Phase 3 guides](<docs/phases guide/phase-3/README.md>) for scope and verification status.

For the Phase 0 changes, detailed file structure, startup flow, and component responsibilities, read the [Phase 0 project foundation guide](<docs/phases guide/phase-0/phase-0-project-foundation.md>).
