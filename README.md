# Agentic Research & Knowledge Assistant

A research workspace for evidence-grounded answers across PDFs. Implementation follows the supplied v2.0 guide, one acceptance gate at a time.

Phase 0 builds the project foundation: Next.js/TypeScript, FastAPI, validated configuration, structured request logs, async PostgreSQL pooling, pgvector migrations, and CI. PDF ingestion, embeddings, retrieval, generation, agent workflows, and cloud deployment belong to later phases and are not implemented yet.

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

See [architecture](docs/architecture.md), [API contracts](docs/api-contracts.md), and [security boundaries](docs/threat-model.md). The next implementation gate is Phase 1: layout-aware PDF ingestion.

For the Phase 0 changes, detailed file structure, startup flow, and component responsibilities, read the [Phase 0 project foundation guide](<docs/phases guide/phase-0-project-foundation.md>).
