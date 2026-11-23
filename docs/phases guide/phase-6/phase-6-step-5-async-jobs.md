# Phase 6, step 5: Persisted asynchronous research jobs

`POST /api/v1/research` validates the request and current session-visible document
scope, persists a queued `ResearchJob`, and returns HTTP 202. The API process then
runs the LangGraph in a background task. Every completed graph node is written to
the job's `steps[]`, along with the current tool-call records, counters, and
retrieved evidence. The final cited report is persisted after the graph finishes.
`GET /api/v1/research/{job_id}` is session-owner scoped and returns 404 for
another session.

The migration adds bounded counters and JSONB progress fields. Startup recovery
marks queued/running jobs older than five minutes as failed with
`INTERRUPTED_BY_RESTART`; jobs are not resumed after a restart. Requests are
limited per session, and all report citations are rechecked against exact stored
chunk text and character offsets before completion.

The web app provides a request form at `/research` and a polling progress/report
view at `/research/{job_id}`. Session bootstrap preserves an existing valid
anonymous session cookie so the UI does not orphan session-owned documents.

## Database and automated verification

From `apps/api`:

```powershell
uv run alembic upgrade head
$env:RUN_DB_TESTS = "1"
uv run pytest -q tests/integration/test_research_jobs_api.py
```

The integration test submits a multi-document job with a deterministic grounded
provider, verifies the persisted node trace and citation, rejects foreign documents,
checks session-owner isolation, and exercises stale-job recovery. Earlier steps
exercise all 40 fixed retrieval questions; this integration test proves the
end-to-end job contract without making a paid/live LLM request.

## Visual example

Start the API and web app, then open `http://localhost:3000/research`. Use the
ready sample documents indexed by the Phase 3 seeder:

- Educational QA: `35d86749-bf13-55ac-8008-231937b43bab`
- Medical QA: `be12ca47-9e95-56c9-abdc-104a9f7680f5`

Enter this question:

```text
Compare the evaluation approaches described in these papers.
```

Submit to open the live job view. It polls until completion and displays the
progress steps, iteration/tool counts, partial-coverage notice if applicable, and
verified source quotes with document IDs and page numbers. The same job can be
inspected in Swagger at `GET /api/v1/research/{job_id}`. A successful HTTP 202
means the job was queued; it does not by itself mean the report passed the
multi-task quality acceptance test.

## Acceptance status

The five implementation steps are complete, but Phase 6's live task-completion
gate is not claimed as passed. The supplied Phase 3 set has 40 single-document
retrieval questions, not the required 25 multi-document synthesis/comparison tasks.
The deterministic integration suite cannot establish the required 85% live
success rate. A reviewed 25-task set and live-model evaluation remain necessary.

## Source

- `apps/api/app/api/v1/research.py` — create/poll API and session-owner checks.
- `apps/api/app/services/research/runner.py` — concrete graph operations and citation
  verification.
- `apps/api/app/db/models.py` and `apps/api/migrations/versions/0005_research_jobs.py`
  — persisted job state.
- `apps/web/app/research/page.tsx` and `apps/web/app/research/[id]/page.tsx` — request
  form and visual progress/report view.
- `apps/api/tests/integration/test_research_jobs_api.py` — end-to-end job checks.
