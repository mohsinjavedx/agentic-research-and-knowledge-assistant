# Phase 6, step 1: Typed graph state

The research workflow starts from a validated multi-document request and a typed
LangGraph state. State fields cover the query, anonymous session, server-resolved
document scope, subquestions, retrieved evidence, tool-call and iteration counters,
sufficiency verdict, final report, workflow status, progress steps, and safe error code.
The request rejects blank queries, duplicate documents, and scopes with fewer than
two document IDs.

## Verification

From `apps/api`:

```powershell
uv run pytest -q tests/unit/test_research_state.py
```

The tests initialize state for every one of the 40 fixed Phase 3 questions and check
the initial counters, status, and evidence fields. They also reject duplicate IDs and
document IDs outside the server-resolved visible scope.

## Visual example

The example below uses two sample-document IDs and a question from the golden
set. Run it from `apps/api` to print the initial state as JSON. In the API workflow,
the allowed IDs must come from the server-resolved visible-document scope:

```powershell
uv run python -c "import json; from uuid import UUID, uuid4; from app.schemas.research import ResearchRequest; from app.services.research.state import initial_research_state; docs=[UUID('35d86749-bf13-55ac-8008-231937b43bab'),UUID('a0fba681-ef99-5f3b-aee3-91ea98269e33')]; request=ResearchRequest(query='Which five benchmarks are used to evaluate the educational question-answering system?',document_ids=docs); print(json.dumps(initial_research_state(request,session_id=uuid4(),allowed_doc_ids=docs),default=str,indent=2))"
```

Expected initial values include `status: "queued"`, empty `subquestions` and
`retrieved_evidence`, `tool_calls_count: 0`, `iterations: 0`, and a null
`sufficiency_verdict`. Once the job endpoint is implemented in step 5, this same
state is inspectable through `GET /api/v1/research/{job_id}` in Swagger.

## Source

- `apps/api/app/schemas/research.py` — request, report, progress, and graph-state types.
- `apps/api/app/services/research/state.py` — validated state initializer.
- `apps/api/tests/unit/test_research_state.py` — golden-query and scope tests.
