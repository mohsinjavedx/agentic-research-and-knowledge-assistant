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
